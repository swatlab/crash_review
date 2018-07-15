# Why Did This Reviewed Code Crash? <br/><sub>An Empirical Study of Mozilla Firefox</sub>

### Requirements
- Python 2.7 or newer

### File description
- **analytic_scripts** folder contains the scripts to mine software repositories (please configure the variable ```HG_REPO_PATH``` as your own Mozilla VCS path in each of the scripts in this folder).
	- **crash_inducing.py**: identify commits that lead to crashes (crash-inducing commits).
	- **basic_metrics.py** and **review_metrics.py**: extract metrics for reviewed patches.
	- **mann-whitney.py**: calculate two tailed Mann-Whiteny U test to compare the differences between reviewed patches that crash and reviewed patches that do not crash as well as Cliff's delta effect size on the differences.
- **statistics** folder contains data extracted from software repositories.
- **data** folder contains data extracted from various software repostories, including Bugzilla, VCS, and Mozilla crash reports.
- **crash_report_examples** folder contains crash report examples downloaded from Mozilla crash archive.

### How to user the analytic scripts
1. Down load Mozilla bug reports via REST API (https://wiki.mozilla.org/Bugzilla:REST_API).
2. Run ```crash_inducing.py``` to identify crash-inducing commits.
3. Run ```basic_metrics.py``` and ```review_metrics.py``` to extract metrics from reviewed patches for statistical analyses.
4. Run ```mann-whitney.py``` to perform different statistical analyses.

### Data source
- Socorro local crash reports are available in:
    https://crash-analysis.mozilla.com
- Firefox' Mercurial repository:
	https://developer.mozilla.org/en-US/docs/Mozilla/Developer_guide/Source_Code/Mercurial

### For any questions
Please send email to le.an@polymtl.ca