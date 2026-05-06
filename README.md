# automate_proceedings (CROS)

This repo contains a bundle of resources for preparing the proceedings of an IEEE conference. The scripts provide utilities to process the pdf files, like:

- get number of pages
- check copyright notice
- check IEEE Express compliance
- get title and authors from pdf
- sort the papers according to the conference presentation schedule
- check if the authors signed the copyright with the correct title and authors
- add number to pages
- create table of contents and author index

## Compliance Check

**Install dependencies**:

```
pip install pypdf
```

**Run**:

```
python3 compliance_check.py /path/to/pdf/directory
```
