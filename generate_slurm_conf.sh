#!/bin/bash -e
sinfo --Node --noheader --format="%N" --responding -p debug |
while read -r node; do
    srun -i /dev/null --nodelist ${node} ./get_slurm_conf.py slurm.conf
done

