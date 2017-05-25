#!/bin/bash -x
while read node; do
    srun --nodelist $node ./get_slurm_conf.py &
done < <(sinfo --Node | tail -n+2 | cut -d" " -f1)

