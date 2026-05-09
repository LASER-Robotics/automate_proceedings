# automate_ieee_proceedings
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-2-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->

This repo contains a bundle of resources for preparing the proceedings of an IEEE conference, specifically the Brazilian Conference on Robotics (CROS). The scripts provide utilities to process the camera-ready pdf files, like:

- get title and authors from pdf
- get number of pages
- check if the pdf template is IEEE RAS
- check copyright notice in the first page
- check if the signed copyright form have the correct title and authors
- check IEEE eXpress compliance
- sort the papers according to the conference presentation schedule
- add number to pages
- create table of contents and author index

## Setup

```
  pip install -r requirements.txt
```

The scripts uses thee inputs:

- A folder `input_data/camera_ready_papers` with the camera-ready pdfs named by ID with three digits (i.e 007.pdf, 069.pdf, 106.pdf, etc)
- The `input_data/SearchCopyright.xlsx` log file from [IEEE eCF Management Toolkit](https://ecopyright.ieee.org/toolkit/landing)
- A csv `input_data/sessions.csv` with all the papers that were presented at the conference (no show papers removed), with the ID, title and session names, given by the program chair. See folder `input_data` for an example.

## How to use
Run the following scripts:

  | Script | Description |
  | :--- | :--- |
  | `camera_ready_check.py` | Process every pdf in the folder `input_data/camera_ready_papers` and returns a csv with: paper title and authors extracted from pdf, number of pages, copyrigt notice in the first page (true/false), ecf status (signed the copyright form) and if the pdf is IEEE eXpress compliant. The script creates another xlsx file that checks for [RAS IEEE PDF template](http://ras.papercept.net/conferences/support/files/ieeeconf.zip). |
  | `sort_pdfs_schedule.py` | Organize the camera-ready pdfs according to the conference sessions schedule, so the pdfs are sorted by order of presentation in folder `pdfs_sorted`. Creates a `reports/final_compliance_report.xlsx` that indicates if the pdf title and authors are different from the ones signed in the copyright form. |
  | `prepare_proceedings.py` | Number pages of the sorted pdfs and creates a table of contents and an author index. The results are stored in folder `numbered_pages`. These are the files used to create the packing list. |

## How to start an IEEE conference

This whole process starts with an [IEEE Conference Application](https://conferences.ieee.org/application/home).

## How to contribute

You can contribute to this project by detecting bugs, proposing (issues) or implementing (pull requests) additional features, and by documenting the conference publication process.

## Contributors

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/davihdsantos"><img src="https://avatars.githubusercontent.com/u/2212793?v=4?s=100" width="100px;" alt="Davi Santos"/><br /><sub><b>Davi Santos</b></sub></a><br /><a href="#projectManagement-davihdsantos" title="Project Management">📆</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/gaabsjrer"><img src="https://avatars.githubusercontent.com/u/139882649?v=4?s=100" width="100px;" alt="Gabriel Lucena"/><br /><sub><b>Gabriel Lucena</b></sub></a><br /><a href="#code-gaabsjrer" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/alyssonm0"><img src="https://avatars.githubusercontent.com/u/143957076?v=4?s=100" width="100px;" alt="Alysson Martim"/><br /><sub><b>Alysson Martim</b></sub></a><br /><a href="#code-alyssonm0" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/HerlanLima"><img src="https://avatars.githubusercontent.com/u/134648192?v=4?s=100" width="100px;" alt="HerlanLima"/><br /><sub><b>HerlanLima</b></sub></a><br /><a href="#code-HerlanLima" title="Code">💻</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

---
