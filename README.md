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

## Setup

```
  pip install -r requirements.txt
```

## How to use

The scripts uses thee inputs:

- a folder with the camera-ready pdfs named by ID with three digits (i.e 001.pdf, 002.pdf, etc)
- the **SearchCopyright.xlsx** log file from [IEEE eCF Management Toolkit](https://ecopyright.ieee.org/toolkit/landing)
- a csv with all the ID and title in order of presentation, given by the program chair

  | Script | Description | Input/Output |
  | :--- | :--- | :--- |
  | `camera_ready_check.py` | This script process every pdf and returns a csv with: paper title, number of pages, initial page number, last page number, copyrigt notice in the first page (true/false), ieee express compliance and if it uses the conference template  | `In: folder path; Out: ` |

## Compliance Check

**Install dependencies**:

```
pip install pypdf
```

**Run**:

```
python3 compliance_check.py /path/to/pdf/directory
```
