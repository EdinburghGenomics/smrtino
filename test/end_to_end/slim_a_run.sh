#!/bin/bash
set -ue
shopt -s nullglob

# Takes a PacBio run folder and makes a mini version of it for you to test on.
#  slim_a_run.sh <run_name_or_path> [dest]
# eg, to copy to the CWD:
# $ test/end_to_end/slim_a_run.sh /lustre-gseg/smrtlink/sequel_seqdata/r64175e_20220412_154747

RUN_PATH="${1:?Give me a PacBio run to slim}"
DEST="${2:-.}"

# Use the TOOLBOX
EXEC_DIR="${EXEC_DIR:-`dirname $BASH_SOURCE`/../..}"
TOOLBOX="$( cd $EXEC_DIR && readlink -f ${TOOLBOX:-toolbox} )"
PATH="${TOOLBOX}:${PATH}"

# If RUN_ID contains no /, assume the normal location (FROM_LOCATION in environ.sh)
if [[ ! "$RUN_PATH" =~ / ]] ; then
    RUN_PATH=/lustre-gseg/smrtlink/sequel_seqdata/"$RUN_PATH"
fi
RUN_ID="`basename $RUN_PATH`"

# Now DEST...
DEST="$DEST/$RUN_ID"

if [ -e "$DEST" ] ; then
  echo "$DEST already exists. Remove it first."
  exit 1
fi

echo "Slimming down $RUN_PATH --> $DEST"

CELLS="`echo "$RUN_PATH"/[0-9]_???`"
echo "Making directories for `wc -w <<<$CELLS` cells."
for cell in $CELLS ; do
    cell=`basename $cell`
    mkdir -p "$DEST"/$cell

    # Copy files for all cells
    for bam in "$RUN_PATH/$cell"/*.bam ; do
        echo "Slimming down `basename $bam` from $RUN_PATH/$cell"
        # Note this leaves less than 1000 reads because there are some header lines, but it will do
        samtools view -h  "$bam" | head -n 1000 | samtools view -b > "$DEST/$cell/`basename $bam`"

        # And re-index
        echo "Running pbindex on `basename $bam`"
        ( cd "$DEST/$cell" && smrt pbindex "`basename $bam`" )
    done

    echo "Copying all other files from $RUN_PATH/$cell"
    cp -v -n -t "$DEST/$cell" "$RUN_PATH/$cell"/*  2>/dev/null || true
done

# Yep it's much simpler than an Illumina run!
tree "$DEST"
echo DONE
