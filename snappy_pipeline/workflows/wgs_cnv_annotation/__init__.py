# -*- coding: utf-8 -*-
"""Implementation of the ``wgs_cnv_annotation`` step

The ``wgs_cnv_annotation`` step takes as the input the results of the ``wgs_cnv_calling`` step
(called germline CNVs) and ``variant_calling`` (called small germline variants) and performs
annotation and filtration of the structural variants.

Such filters include:

- quality filter for removing calls with low support,
- inheritance compatibility filter that checks for compatibility of inheritance (only works
  for trios currently),
- various filters related to lower the false discovery rate in rare/de novo variant calling,
  e.g., counting number of affected individuals in cohort outside the index' family.

.. note::

    Status: not implemented yet

==========
Step Input
==========

The variant annotation step uses the output of the following CUBI pipeline steps:

- ``wgs_cnv_calling``
- ``variant_annotation``

===========
Step Output
===========

.. note: TODO

====================
Global Configuration
====================

.. note: TODO

=====================
Default Configuration
=====================

The default configuration is as follows.

.. include:: DEFAULT_CONFIG_wgs_cnv_annotation.rst

=======
Reports
=======

Currently, no reports are generated.
"""

import os
import sys

from biomedsheets.shortcuts import GermlineCaseSheet, is_not_background
from snakemake.io import expand

from snappy_pipeline.utils import dictify, listify
from snappy_pipeline.workflows.abstract import (
    BaseStep,
    BaseStepPart,
    LinkOutStepPart,
    ResourceUsage,
    WritePedigreeStepPart,
)
from snappy_pipeline.workflows.ngs_mapping import NgsMappingWorkflow
from snappy_pipeline.workflows.wgs_cnv_calling import WgsCnvCallingWorkflow

__author__ = "Manuel Holtgrewe <manuel.holtgrewe@bih-charite.de>"

#: Extensions of files to create as main payload
EXT_VALUES = (".vcf.gz", ".vcf.gz.tbi", ".vcf.gz.md5", ".vcf.gz.tbi.md5")

#: Names of the files to create for the extension
EXT_NAMES = ("vcf", "vcf_tbi", "vcf_md5", "vcf_tbi_md5")

#: Default configuration of the wgs_cnv_filtration step
DEFAULT_CONFIG = r"""
# Default configuration wgs_cnv_annotation
step_config:
  wgs_cnv_annotation:
    path_ngs_mapping: ../ngs_mapping
    path_wgs_cnv_calling: ../wgs_cnv_calling
    tools_ngs_mapping: [bwa]           # REQUIRED
    tools_wgs_cnv_calling: [erds_sv2]  # REQUIRED
"""


class VcfCnvFilterStepPart(BaseStepPart):
    """Annotate VCF using wgs_cnv_filter.py script."""

    #: Step name
    name = "vcf_cnv_filter"

    #: Class available actions
    actions = ("run",)

    def __init__(self, parent):
        super().__init__(parent)
        self.base_path_out = "work/{mapper}.{caller}.annotated.{index_ngs_library}/out/.done"
        self.log_path = (
            "work/{mapper}.{caller}.annotated.{index_ngs_library}/"
            "log/snakemake.wgs_cnv_filter.log"
        )

    def get_input_files(self, action):
        """Return input function returning input file dict."""

        @dictify
        def input_function(wildcards):
            # Validate action
            self._validate_action(action)
            # Pedigree file
            tpl = "work/write_pedigree.{index_ngs_library}/out/{index_ngs_library}.ped"
            yield "ped", tpl.format(**wildcards)
            # SVs
            key_ext = {"vcf": ".vcf.gz", "vcf_tbi": ".vcf.gz.tbi"}
            tpl = (
                "output/{mapper}.{caller}.{index_ngs_library}/out/"
                "{mapper}.{caller}.{index_ngs_library}"
            )
            wgs_cnv_calling = self.parent.sub_workflows["wgs_cnv_calling"]
            for key, ext in key_ext.items():
                yield key, wgs_cnv_calling(tpl + ext).format(**wildcards)

        return input_function

    @dictify
    def get_output_files(self, action):
        """Return output files for the filtration"""
        # Validate action
        self._validate_action(action)
        prefix = (
            "work/{mapper}.{caller}.annotated.{index_ngs_library}/out/"
            "{mapper}.{caller}.annotated.{index_ngs_library}"
        )
        key_ext = {
            "vcf": ".vcf.gz",
            "vcf_tbi": ".vcf.gz.tbi",
            "vcf_md5": ".vcf.gz.md5",
            "vcf_tbi_md5": ".vcf.gz.tbi.md5",
        }
        for key, ext in key_ext.items():
            yield key, prefix + ext

    def get_log_file(self, action):
        # Validate action
        self._validate_action(action)
        return self.log_path

    def get_resource_usage(self, action):
        """Get Resource Usage

        :param action: Action (i.e., step) in the workflow, example: 'run'.
        :type action: str

        :return: Returns ResourceUsage for step.
        """
        # Validate action
        self._validate_action(action)
        return ResourceUsage(
            threads=2,
            time="4-04:00:00",  # 4 days and 4 hours
            memory=f"{5 * 1024 * 2}M",
        )


class WgsCnvAnnotationWorkflow(BaseStep):
    """Perform germline WGS SV annotation"""

    #: Workflow name
    name = "wgs_cnv_annotation"

    #: Default biomed sheet class
    sheet_shortcut_class = GermlineCaseSheet

    @classmethod
    def default_config_yaml(cls):
        """Return default config YAML, to be overwritten by project-specific one"""
        return DEFAULT_CONFIG

    def __init__(self, workflow, config, config_lookup_paths, config_paths, workdir):
        super().__init__(
            workflow,
            config,
            config_lookup_paths,
            config_paths,
            workdir,
            (WgsCnvCallingWorkflow, NgsMappingWorkflow),
        )
        # Register sub step classes so the sub steps are available
        self.register_sub_step_classes(
            (WritePedigreeStepPart, VcfCnvFilterStepPart, LinkOutStepPart)
        )
        # Register sub workflows
        self.register_sub_workflow("ngs_mapping", self.config["path_ngs_mapping"])
        self.register_sub_workflow("wgs_cnv_calling", self.config["path_wgs_cnv_calling"])
        # Copy over "tools" setting from wgs_cnv_calling/ngs_mapping if not set here
        if not self.config["tools_ngs_mapping"]:
            self.config["tools_ngs_mapping"] = self.w_config["step_config"]["ngs_mapping"]["tools"][
                "dna"
            ]
        if not self.config["tools_wgs_cnv_calling"]:
            self.config["tools_wgs_cnv_calling"] = self.w_config["step_config"]["variant_calling"][
                "tools"
            ]

    @listify
    def get_result_files(self):
        """Return list of result files for the NGS mapping workflow

        We will process all primary DNA libraries and perform joint calling within pedigrees
        """
        name_pattern = "{mapper}.{caller}.annotated.{index_library.name}"
        yield from self._yield_result_files(
            os.path.join("output", name_pattern, "out", name_pattern + "{ext}"),
            mapper=self.config["tools_ngs_mapping"],
            caller=self.config["tools_wgs_cnv_calling"],
            ext=EXT_VALUES,
        )

    def _yield_result_files(self, tpl, **kwargs):
        """Build output paths from path template and extension list"""
        for sheet in filter(is_not_background, self.shortcut_sheets):
            for pedigree in sheet.cohort.pedigrees:
                if not pedigree.index:
                    msg = "INFO: pedigree without index (names: {})"
                    print(
                        msg.format(list(sorted(d.name for d in pedigree.donors))), file=sys.stderr
                    )
                    continue
                elif not pedigree.index.dna_ngs_library:  # pragma: no cover
                    msg = "INFO: pedigree index without DNA NGS library (names: {})"
                    print(
                        msg.format(  # pragma: no cover
                            list(sorted(d.name for d in pedigree.donors))
                        ),
                        file=sys.stderr,
                    )
                    continue  # pragma: no cover
                yield from expand(tpl, index_library=[pedigree.index.dna_ngs_library], **kwargs)

    def check_config(self):
        """Check that the path to the NGS mapping is present"""
        self.ensure_w_config(
            ("step_config", "wgs_cnv_annotation", "tools_ngs_mapping"),
            "NGS mapping tools not configured but required for WGS SV annotation",
        )
        self.ensure_w_config(
            ("step_config", "wgs_cnv_annotation", "tools_wgs_cnv_calling"),
            "WGS SV calling tools not configured but required for WGS SV annotation",
        )
