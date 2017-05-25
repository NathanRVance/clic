#!/usr/bin/perl

use strict;
use warnings;

use CGI;

print CGI::header();

print "<html> <head>\n";
print "<title>CLIC</title>";
print "</head>\n";
print "<body>\n";
print "<h1>CLIC: CLuster In the Cloud</h1>\n";
print "<p>" . `sudo cat /var/log/clic.log | sed 's/\$/<br>/g'` . "</p>\n";
print "</body> </html>\n";
