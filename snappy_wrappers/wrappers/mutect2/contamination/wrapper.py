# -*- coding: utf-8 -*-
"""CUBI+Snakemake wrapper code for MuTect 2: Snakemake wrapper.py
"""

from snakemake import shell

__author__ = "Manuel Holtgrewe <manuel.holtgrewe@bih-charite.de>"

reference = snakemake.config["static_data_config"]["reference"]["path"]

shell.executable("/bin/bash")

shell(
    r"""
set -x

# export JAVA_HOME=$(dirname $(which gatk))/..
export LD_LIBRARY_PATH=$(dirname $(which bgzip))/../lib

# Also pipe everything to log file
if [[ -n "{snakemake.log}" ]]; then
    if [[ "$(set +e; tty; set -e)" != "" ]]; then
        rm -f "{snakemake.log}" && mkdir -p $(dirname {snakemake.log})
        exec &> >(tee -a "{snakemake.log}" >&2)
    else
        rm -f "{snakemake.log}" && mkdir -p $(dirname {snakemake.log})
        echo "No tty, logging disabled" >"{snakemake.log}"
    fi
fi

# TODO: add through shell.prefix
export TMPDIR=/fast/users/$USER/scratch/tmp

# Setup auto-cleaned TMPDIR
export TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT
mkdir -p $TMPDIR/out

out_base=$TMPDIR/out/$(basename {snakemake.output.table} .contamination.tbl)

gatk --java-options '-Xms4000m -Xmx8000m' CalculateContamination \
    --input {snakemake.input.tumor} \
    --matched-normal {snakemake.input.normal} \
    --tumor-segmentation ${{out_base}}.segments.tbl \
    --output ${{out_base}}.contamination.tbl

pushd $TMPDIR && \
    for f in $out_base.*; do \
        md5sum $f >$f.md5; \
    done && \
    popd

mv $out_base.* $(dirname {snakemake.output.table})
"""
)
