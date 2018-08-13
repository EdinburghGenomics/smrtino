#!/usr/bin/perl

=head1 NAME

subread_stats.pl - Takes one or more fasta files as input and calculates some assembly stats for it

=head1 SYNOPSIS

subread_stats.pl -fasta /path/to/file1.fasta -fasta /path/to/file2.fasta -threshold 100 -delim ","

=head1 DESCRIPTION

subread_stats.pl takes one or more fasta files as input and calculates subread stats such as number, total assembled bases, N50,
for each subread size cutoff. If you have R installed, it also gives you pretty plots

=head1 AUTHORS

sujai.kumar@ed.ac.uk 2010.05.12

=cut

use strict;
use warnings;
use Getopt::Long qw(:config pass_through no_ignore_case);

my @fastafiles;
my @covfiles;
my @thresholds;
my $delim = ",";
my $output_dir = "pc";
my $graphs = "";
my $length_cutoff;
my $humanread;

GetOptions (
    "fastafile=s{,}" => \@fastafiles,
    "covfile=s{,}"   => \@covfiles,
    "threshold=i{,}" => \@thresholds,
    "delimiter=s" => \$delim,
    "output=s"    => \$output_dir,
    "graphs"      => \$graphs,
    "length=i"    => \$length_cutoff,
    "human"       => \$humanread,
);
@thresholds = (100,1000) unless @thresholds;

#---------------------------------

die <<USAGE

Usage: subread_stats.pl -f subreads1.fa -c subreads1.fa.cov -f subreads2.fa -c subreads2.fa.cov -t 100 -t 1000 -d "," -g
-t threshold values are optional (default -t 100)
-c cov files (corresponding to -f fasta files) are also optional and are tab delimited files where col 1 is subread id and col 2 is coverage
-g generates a cumulative subread length graph (needs R installed)
-l length removes subreads less than length. Stats are reported at the cutoffs used, but the graph is produced with all subread lengths.
   Using -l creates the graph with subreads that have this minimum length.

USAGE
unless @fastafiles;

if (-e $output_dir) {
    print STDERR "$output_dir exists, will be overwritten\n";
    system "rm -rf $output_dir";
}
mkdir $output_dir or die "Could not create $output_dir\nCheck if you have permission\n";

my $toprint = "";

# print header of table
$toprint .= "Filename${delim}Max subread length";
foreach (@thresholds) {
    $toprint .= "${delim}Num subreads >=$_${delim}Total bases in subreads >=$_${delim}N50 for subreads >=$_${delim}GC subreads >=$_${delim}Mean length for subreads >=$_";
}
$toprint .= "\n";

my %sequences_all;
for my $fastafile (@fastafiles) {

    # Read in subreads from fasta files
    $sequences_all{$fastafile} = &fastafile2hash($fastafile);
    my @sorted_subreads =
        sort { $sequences_all{$fastafile}{$b}{len} <=> $sequences_all{$fastafile}{$a}{len} }
            keys % { $sequences_all{$fastafile} };
    my $longest_subread = $sequences_all{$fastafile}{$sorted_subreads[0]}{len};

    my $covfile;
    if (@covfiles) {
        $covfile = shift @covfiles;
        $sequences_all{$fastafile} = &addCoverage2Hash ($sequences_all{$fastafile}, $covfile);
    }
    &printSubreadLengths($output_dir, $fastafile, $sequences_all{$fastafile});

    $toprint .= "$fastafile${delim}$longest_subread";

    # for each cutoff
    for my $threshold (@thresholds) {
        my $num_subreads = 0;
        my $total_bases = 0;
        my $N50 = 0;
        my $subreads_in_N50 = 0;
        my $gc_count = 0;
        my $total_nonatgc = 0;

        # calculate num subreads, total bases and gc count at this cutoff
        for my $subread (@sorted_subreads) {
            my $subread_len = $sequences_all{$fastafile}{$subread}{len};
            last if $subread_len < $threshold;
            $num_subreads++;
            $total_bases   += $subread_len;
            $total_nonatgc += $sequences_all{$fastafile}{$subread}{nonatgc};
            $gc_count      += $sequences_all{$fastafile}{$subread}{gc};
        }
        my $mean_subread_length;
        $mean_subread_length = $total_bases/$num_subreads if $num_subreads >0;

        # calculate N50
        my $cumulative_total = 0;
        for my $subread (@sorted_subreads) {
            my $subread_len = $sequences_all{$fastafile}{$subread}{len};
            $cumulative_total += $subread_len;
            $N50 = $subread_len;
            $subreads_in_N50 ++;
            last if ($cumulative_total > $total_bases/2);
        }

        if ($total_bases > 0) {
            $toprint .= "${delim}$num_subreads${delim}$total_bases${delim}$N50${delim}" .
                        sprintf("%.1f",$gc_count*100/($total_bases - $total_nonatgc + 1)) .
                        ${delim} . sprintf("%.1f",$mean_subread_length);
        }
        else {
            $toprint .= "${delim}0${delim}0${delim}NA${delim}NA${delim}NA";
        }
    }
    # new line at end of subread stats row for each fasta file
    $toprint .= "\n";
}
open  STAT, ">$output_dir/subread_stats.txt" or die $!;
print STAT $toprint;
close STAT;
if ($humanread) {
  my $delimpattern="\\$delim";
  my @toprint_rows = map [split(/$delimpattern/,$_)], split(/\n/, $toprint);
  for (my $i=0; $i < @{$toprint_rows[0]}; $i++) {
    for (my $j=0; $j < @toprint_rows; $j++) {
      print $toprint_rows[$j][$i] . $delim;
    }
    print "\n";
  }
}


#############################################################################

sub fastafile2hash {
    my $fastafile = shift @_;
    my %sequences_lengc;
    my $fh = &read_fh($fastafile);
    my $header;
    while (my $line = <$fh>) {
        if ($line =~ /^>(\S+)(.*)/) {
            $header = $1;
            # $sequences{$header}{desc} = $2;
        }
        else {
            chomp $line;
            $sequences_lengc{$header}{len} += length $line;
            $sequences_lengc{$header}{gc}  += ($line =~ tr/gcGC/gcGC/);
            $line =~ s/[^atgc]/N/ig;
            $sequences_lengc{$header}{nonatgc} += ($line =~ tr/N/N/);
        }
    }
    close $fh;
    if ($length_cutoff) {
        foreach (keys %sequences_lengc) {
            delete $sequences_lengc{$_} if $sequences_lengc{$_}{len} < $length_cutoff;
        }
    }
    return \%sequences_lengc;
}

#############################################################################

sub addCoverage2Hash {
    my ($sequences_cov, $covfile) = @_;

    # takes coverage info for each subread from covfile, and attaches as cov field to each subread id key
    my $fh = &read_fh($covfile);
    while (my $line = <$fh>) {
        next unless $line =~ /^(\S+)\t(\S+)$/;
        $$sequences_cov{$1}{cov} = $2 if (defined $$sequences_cov{$1})
    }
    return $sequences_cov;
}

#############################################################################

sub printSubreadLengths {
    my ($output_dir, $fastafile, $sequences) = @_;

    open LEN, ">>$output_dir/subread_lengths_gc.txt" or die $!;
    foreach (keys %{$sequences}) {
        print LEN "$fastafile\t$_\t$$sequences{$_}{len}\t$$sequences{$_}{gc}\t$$sequences{$_}{nonatgc}";
        print LEN "\t$$sequences{$_}{cov}" if exists $$sequences{$_}{cov};
        print LEN "\n";
    }
    close LEN;
}

#############################################################################

sub read_fh {
    my $filename = shift @_;
    my $filehandle;
    if ($filename =~ /gz$/) {
        open $filehandle, "gunzip -dc $filename |" or die $!;
    }
    else {
        open $filehandle, "<$filename" or die $!;
    }
    return $filehandle;
}
