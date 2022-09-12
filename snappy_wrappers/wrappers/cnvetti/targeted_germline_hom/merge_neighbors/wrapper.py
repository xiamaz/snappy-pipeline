# -*- coding: utf-8 -*-

import os
import sys

from snakemake.shell import shell

# The following is required for being able to import snappy_wrappers modules
# inside wrappers.  These run in an "inner" snakemake process which uses its
# own conda environment which cannot see the snappy_pipeline installation.
base_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
sys.path.insert(0, base_dir)

from snappy_wrappers.tools import vcf_cnvetti_coverage_to_hom_del_calls  # noqa: E402

vcf_cnvetti_coverage_to_hom_del_calls.main([snakemake.output.vcf, snakemake.input.vcf])

shell(
    r"""
set -x
set -euo pipefail

cd $(dirname {snakemake.output.vcf})
cp $(basename {snakemake.output.vcf}) $(basename {snakemake.output.vcf}).bak
tabix -f $(basename {snakemake.output.vcf})

md5sum $(basename {snakemake.output.vcf}) >$(basename {snakemake.output.vcf}).md5
md5sum $(basename {snakemake.output.vcf}.tbi) >$(basename {snakemake.output.vcf}).tbi.md5
"""
)
