#!/bin/bash
set -euo pipefail
shopt -s nullglob

# Allow VERBOSE to forcibly override the environ.sh setting
_verbose="${VERBOSE:-}"

# Load the settings for this pipeline.
SMRTINO_HOME="$(readlink -f $(dirname $BASH_SOURCE)/..)"
ENVIRON_SH="${ENVIRON_SH:-$SMRTINO_HOME/environ.sh}"
if [ -e "$ENVIRON_SH" ] ; then
    pushd "`dirname $ENVIRON_SH`" >/dev/null
    source "`basename $ENVIRON_SH`"
    popd >/dev/null

    export BACKUP_LOCATION    FROM_LOCATION    BACKUP_FROM_LOCATION \
           BACKUP_NAME_REGEX  RUN_NAME_REGEX   BACKUP_CUTOFF_DAYS \
           VERBOSE            BACKUP_DRY_RUN
fi

# Add the PATH
PATH="$SMRTINO_HOME:$PATH"
VERBOSE="${_verbose:-${VERBOSE:-0}}"

# Set defaults
BACKUP_FROM_LOCATION="${BACKUP_FROM_LOCATION:-$FROM_LOCATION}"
BACKUP_NAME_REGEX=("${BACKUP_NAME_REGEX:-${RUN_NAME_REGEX[@]}}")
BACKUP_CUTOFF_DAYS="${BACKUP_CUTOFF_DAYS:-90}"

# Optional echo
debug(){ if [ "${VERBOSE}" != 0 ] ; then echo "$@" ; fi ; }

# "mkdir -p" that works on remote host
mkdir_p(){
    if [[ "$1" =~ : ]] ; then
        ssh "${1%:*}" mkdir -vp "${1#*:}"
    else
        mkdir -vp "$1"
    fi
}

# The config file must provide a valid BACKUP_FROM_LOCATION and BACKUP_LOCATION,
# assuming they were not already set in the environment. To explicitly ignore the environ.sh
# do something like:
# $ env ENVIRON_SH=/dev/null FROM_LOCATION=foo BACKUP_LOCATION=bar sync_to_backup_location.sh

debug "Checking that \$BACKUP_FROM_LOCATION and \$BACKUP_LOCATION are existing directories."
stat "$BACKUP_FROM_LOCATION"/ >/dev/null
rsync --list-only "$BACKUP_LOCATION"/. >/dev/null
debug 'Yup :-)'

# Where are runs coming from?
# Where are runs going to (can be a local directory or host:/path)?
echo "Backing up  data from $BACKUP_FROM_LOCATION to $BACKUP_LOCATION"

# We can supply a BACKUP_NAME_REGEX or fall back to RUN_NAME_REGEX (the default here
# should match the one hard-coded in driver.sh). Note that this can be a list of regexes
# and can match into subdirectories.
BACKUP_NAME_REGEX="${BACKUP_NAME_REGEX:-.*_.*_.*}"
debug "BACKUP_NAME_REGEX=(${BACKUP_NAME_REGEX[*]})"
echo ===

# Now loop through all the projects in a similar manner to the driver. We're
# duplicating the funky logic that matches regexes recursively. I'd make this shared
# code but cleanly passing lists to funtions in Bash is not really a thing.

# Generate a list of prefixes from $BACKUP_NAME_REGEX and store the list
# to PREFIX_BACKUP_NAME_REGEX for use in the search logic.
for rnregex in "${BACKUP_NAME_REGEX[@]}" ; do
    # Loop through prefixes up to the first / seen, for which
    # we can use a regex on the regex.
    while [[ "$rnregex" =~ (.+)/(.+) ]] ; do
        rnregex="${BASH_REMATCH[1]}"
        PREFIX_BACKUP_NAME_REGEX+=("$rnregex")
    done
done
debug "PREFIX_BACKUP_NAME_REGEX is (${PREFIX_BACKUP_NAME_REGEX[@]})"

pushd "$BACKUP_FROM_LOCATION" >/dev/null
candidate_run_list=(*/)

while [[ "${#candidate_run_list[@]}" > 0 ]] ; do

  # Shift the first item off the list
  run_basename="${candidate_run_list[0]%/}"
  candidate_run_list=("${candidate_run_list[@]:1}")

  # Never backup paths that are symlinked
  if [ -L "$run_basename" ] ; then
    echo "Ignoring symlink $run_basename"
    continue
  fi

  # Scan for full matches, indicating we have a run
  match_found=0
  for rnregex in "${BACKUP_NAME_REGEX[@]}" ; do
    if [[ "$run_basename" =~ ^${rnregex}$ ]] ; then
      match_found=$(( $match_found + 1 ))
    fi
  done

  if [[ $match_found = 0 ]] ; then
    for prnregex in "${PREFIX_BACKUP_NAME_REGEX[@]}" ; do
      if [[ "$run_basename" =~ ^${prnregex}$ ]] ; then
        # Add the directory contents to the front of the candidate list for consideration,
        # then continue the main loop.
        candidate_run_list=("$run_basename"/*/ "${candidate_run_list[@]}")
        continue 2
      fi
    done

    # If no match, we can prune this whole directory from further searching
    echo "Ignoring $run_basename"
    continue
  fi

  # Apply the $BACKUP_CUTOFF_DAYS filter
  if [ -n "$BACKUP_CUTOFF_DAYS" -a "$BACKUP_CUTOFF_DAYS" != 0 ] ; then
    if ! find "$run_basename" -maxdepth 1 -mtime -"$BACKUP_CUTOFF_DAYS" | grep -q . ; then
        echo "Ignoring run $run_basename with nothing newer than $BACKUP_CUTOFF_DAYS days"
        continue
    fi
  fi

  # Now we have a run that matches a regex. Do we back it up?
  echo "Backing up $run_basename"

  if [ "${BACKUP_DRY_RUN:-0}" != 0 ] ; then
    echo "*** DRY_RUN - skipping ***"
    continue
  fi

  excludes=()
  mkdir_p "$BACKUP_LOCATION/$run_basename"
  rsync -rlpt -sbv "${excludes[@]}" "$run_basename"/ "$BACKUP_LOCATION/$run_basename"/
done
