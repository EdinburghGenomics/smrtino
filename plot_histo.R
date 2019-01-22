#!/usr/bin/env Rscript
library(argparser, quietly=TRUE)
library (ggplot2, quietly=TRUE)
p <- arg_parser("Create binned subread histogram")

# Add command line arguments & parse
p <- add_argument(p, "--bins",   help="Read length bin boundaries", default = "1K,2K,3K,5K,10K,50K,100K")
p <- add_argument(p, "--file",   help="Table file of histogram data", nargs = 1)
p <- add_argument(p, "--output", help = "Output PNG file, please specify as 'x.png'", default = 'plot_histo_R.png')
p <- add_argument(p, "--title", help = "Title to add to the plot", default = "")
p <- add_argument(p, "--color", help = "Fill colour", default = "blue")
p <- add_argument(p, "--size", help = "Plot size", default = "1000x600")
argv <- parse_args(p)

# Do work based on the passed arguments
data<-read.table(argv$file)
bins<-strsplit(argv$bins, ",")
bins<-c("0",gsub("K|k","000",bins[[1]]))
bins<-unique(sort(as.numeric(bins)))
if(tail(bins,n=1) < max(data$V1)+1){bins<-append(bins,max(data$V1)+1)}

# Set output to the desired file. On a headless system we need to do this before plotting
# or we get "Error in grid.newpage() : no active or default device"
geom<-as.integer(unlist(strsplit(argv$size, "x")))
png(argv$output,
    width  = geom[1],
    height = geom[2] )

# Make & save the 'histogram'.
# The use of V1+1 is because we consider, say, 10 to belong in the [10,20) bin whereas ggplot
# sees the bins as (10,20] and puts 10 into the (0,10] bin. And zero-length items vanish entirely.
# The quickest fix for this is to just add 1 to everything
ggplot(data = data, aes(V1+1,V2))+
  stat_summary_bin(fun.y='sum', breaks=bins, geom='col', fill=argv$color, color="black")+
  labs(y="Frequency", x="Read Length", title=argv$title)+
  theme_light()

