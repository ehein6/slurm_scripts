#!/bin/bash
while read node; do
    sbatch --nodelist $node ./get_slurm_conf.py
done < <(sinfo --Node --noheader --format="%N" --responding -p c8)

