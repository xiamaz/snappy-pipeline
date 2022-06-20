# -*- coding: utf-8 -*-
"""Definition for Jannovar germline annotation in parallel, genome is split into windows

isort:skip_file
"""

import os
import sys

# A hack is required for being able to import snappy_wrappers modules when in development mode.
# TODO: is there a more elegant way?
base_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, base_dir)

from snappy_wrappers.resource_usage import ResourceUsage
from snappy_wrappers.wrapper_parallel import (
    ParallelVariantAnnotationBaseWrapper,
    gib_to_string,
    hours,
)


class ParallelJannovarAnnotateVcfWrapper(ParallelVariantAnnotationBaseWrapper):
    """Parallel execution of germline ``jannovar annotate-vcf``."""

    inner_wrapper = "jannovar/annotate_vcf"
    step_name = "variant_annotation"
    tool_name = None  # tool confg is on top level

    def __init__(self, snakemake):
        super().__init__(snakemake)
        self.job_resources = ResourceUsage(
            threads=1,
            memory=gib_to_string(16.0 * self.get_job_mult_memory()),
            time=hours(4 * self.get_job_mult_time()),
            partition=os.getenv("SNAPPY_PIPELINE_PARTITION"),
        )
        self.merge_resources = ResourceUsage(
            threads=2,
            memory=gib_to_string(2.0 * self.get_merge_mult_memory()),
            time=hours(4 * self.get_merge_mult_time()),
            partition=os.getenv("SNAPPY_PIPELINE_PARTITION"),
        )
