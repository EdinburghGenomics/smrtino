#!/bin/sh

# This shell script needs to take a single argument (a FASTQ file) and
# align the reads within to the SILVA database, writing SAM to STDOUT
BASE="/mnt/lustre/e1000/home/edg01/edg01/shared"

# It should respect the SNAKEJOB_THREADS setting.
"$BASE"/software/minimap2/minimap2-2.26_x64-linux/minimap2 \
    -a -t ${SNAKEJOB_THREADS:-3} -x asm10 \
    "$BASE"/references/silva/silva138/SILVA_138.1_LSU_SSU_NR99.fasta \
    "$1"

# Note - I came up with the above database and threads combo through guesswork!
