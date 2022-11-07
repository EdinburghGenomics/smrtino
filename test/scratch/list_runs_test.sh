#!/bin/bash
set -euo pipefail
shopt -sq failglob

FROM_LOCATION=${FROM_LOCATION:-/lustre-gseg/smrtlink/sequel_seqdata}
TO_LOCATION=${TO_LOCATION:-~/test_pacbio_data}

RUN_NAME_REGEX="${RUN_NAME_REGEX:-r.*_[0-9]{8\}_.*}"

RUN_NAME_REGEX=('r64175e_.+_.+' '2.*/.*' 'trash*/foo/bar' 'K[0-9]+/r64175e_.+_.+' 'r64175e_.+_.+')

for d in "$FROM_LOCATION" "$TO_LOCATION" ; do
    if ! [ -d "$d" ] ; then
        echo "No such directory '$d'" >&2
        exit 1
    fi
done


echo "Looking for runs in $FROM_LOCATION"
echo "Matching: (${RUN_NAME_REGEX[@]})"

echo "### Original strat ###"

for run in "$FROM_LOCATION"/*/ ; do
  if ! [[ "`basename $run`" =~ ^${RUN_NAME_REGEX}$ ]] ; then
    echo "Ignoring $(basename $run)"
    continue
  fi

  echo "Processing run $(basename $run)"
done


echo "### New strat ###"

# Generate a list of prefixes from $RUN_NAME_REGEX and store it
# to PREFIX_RUN_NAME_REGEX
for rnregex in "${RUN_NAME_REGEX[@]}" ; do
    # Loop through the location of / characters seen, for which
    # we can use a regex on a regex.
    while [[ "$rnregex" =~ (.+)/(.+) ]] ; do
        rnregex="${BASH_REMATCH[1]}"
        PREFIX_RUN_NAME_REGEX+=("$rnregex")
    done
done
echo "PREFIX_RUN_NAME_REGEX is (${PREFIX_RUN_NAME_REGEX[@]})"


pushd "$FROM_LOCATION" >/dev/null
candidate_run_list=(*/)

while [[ "${#candidate_run_list[@]}" > 0 ]] ; do
  # Shift the first item off the list
  run_basename="${candidate_run_list[0]%/}"
  run_dir="$FROM_LOCATION/$run_basename"
  candidate_run_list=("${candidate_run_list[@]:1}")

  match_found=0
  # Scan for full matches
  for rnregex in "${RUN_NAME_REGEX[@]}" ; do
    if [[ "$run_basename" =~ ^${rnregex}$ ]] ; then
      match_found=$(( $match_found + 1 ))
    fi
  done

  if [[ $match_found = 0 ]] ; then
    for prnregex in "${PREFIX_RUN_NAME_REGEX[@]}" ; do
      if [[ "$run_basename" =~ ^${prnregex}$ ]] ; then
        # Add the directory contents to the stack for consideration,
        # then continue the main loop.
        candidate_run_list=("$run_basename"/*/ "${candidate_run_list[@]}")
        continue 2
      fi
    done

    echo "Ignoring $run_basename"
    continue
  fi

  echo "Processing run $run_dir"

done

