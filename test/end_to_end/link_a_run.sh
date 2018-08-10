#!/bin/bash
set -ue
shopt -s nullglob

# Takes a PacBio run folder and makes a linked version of it for you to test on.
# eg:
# $ test/end_to_end/slim_a_run.sh r54041_20180518_131155 ~/test_sequel

RUN_PATH="${1:?Give me a PacBio run to shallow copy}"
DEST="${2:-.}"

# If RUN_ID contains no /, assume /ifs/sequel
if [[ ! "$RUN_PATH" =~ / ]] ; then
    RUN_PATH=/ifs/sequel/"$RUN_PATH"
fi
RUN_ID="`basename $RUN_PATH`"

# Now DEST...
DEST="$DEST/$RUN_ID"

if [ -e "$DEST" ] ; then
  echo "$DEST already exists. Remove it first."
  exit 1
fi

echo "Shallow copying $RUN_PATH --> $DEST"

CELLS="`echo "$RUN_PATH"/[0-9]_???`"
echo "Making directories for `wc -w <<<$CELLS` cells."
for cell in $CELLS ; do
    cell=`basename $cell`
    mkdir -p "$DEST"/$cell

    # Copy files for all cells
    for bam in "$RUN_PATH/$cell"/*.bam ; do
        echo "Symlinking `basename $bam` from $RUN_PATH/$cell"
        ln -svn "$bam" "$DEST/$cell/`basename $bam`"
    done

    echo "Copying all other files from $RUN_PATH/$cell"
    cp -v -n -t "$DEST/$cell" "$RUN_PATH/$cell"/*  2>/dev/null || true
done

# Yep it's much simpler than an Illumina run!
tree "$DEST"
echo DONE
