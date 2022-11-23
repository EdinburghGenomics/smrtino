At some point we'll start doing backups to the tape library at ACF. (Haha)

But for now we have FluidFS. I'll back up everything to there so we have a copy.

This time we're just backing up the original directories from
/lustre-gseg/smrtlink/sequel_seqdata/ to /fluidfs/sequel/lustre_backup/
There are no output files here so we can back up everything.

We should respect the settings in:
BACKUP_FROM_LOCATION (defaults to FROM_LOCATION)

BACKUP_NAME_REGEX (defaults to RUN_NAME_REGEX and may be multiple runs)

BACKUP_LOCATION=/fluidfs/f1/fastqdata_copy

I don't think we need to skip scanning older runs because the number of files is very smol,
so we can just loop through the runs and rsync.
However, I think skipping any runs older than a month is still reasonable.

OK, cool.
