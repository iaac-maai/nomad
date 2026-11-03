# Floor-plan libraries and generators for training NOMAD's plan AI (3 Nov 2026)

Finch3D's own library is not public. These are the open or requestable alternatives, checked today. Licences are as
stated by each source; confirm on the source page before downloading.

## Datasets
| Dataset | Size | Where from | Licence / access | Fit for NOMAD |
|---|---|---|---|---|
| Swiss Dwellings v3 (have) | 45,000+ flats | Switzerland | CC BY 4.0 | European flats, metric, rooms + doors + windows. We use only 8,625 squared flats today |
| ResPlan (have) | 17,000 plans, vector + room graphs | South Asia | CC BY 4.0 data, MIT code (github.com/m-agour/ResPlan) | Vector graphs ready for training |
| MSD, Modified Swiss Dwellings | 5,300 building floors, 18,900 apartments, ML-ready graphs + structure | Switzerland | CC BY 4.0 (4TU.ResearchData metadata) | Built for training plan generators; whole floors with structure, close to our buildings |
| RPLAN | 80,788 plans | Asia | Research-only, by request to the authors, no redistribution | The set most published generators are trained on |
| LIFULL HOME'S | about 5.1 million plan images | Japan | Free for researchers at universities, by application to NII (www.nii.ac.jp/dsc/idr/lifull/) | Huge, but images (needs reading into vectors) |
| CubiCasa5K | 5,000 plans | Finland | Licence to check on the GitHub repo; Zenodo zip 5.5 GB | Images + annotations, European |
| 3D-FRONT | 6,813 houses | China | Academic licence (to confirm, Alibaba Tianchi) | Furnished 3D layouts |
| FloorPlanCAD | 15,000 CAD plans | China | Hugging Face mirror | Symbols, not rooms: for the plan reader, not generation |

**Usable today without asking anyone:** Swiss Dwellings + ResPlan + MSD, about 80,000 apartments, all CC BY 4.0.

## Generators with open code (boundary in, plan out: what Finch's "fill this outline" needs)
| Model | Input | Code / weights | Licence |
|---|---|---|---|
| GSDiff (AAAI 2025), github.com/SizheHu/GSDiff | outline (boundary-constrained), or room graph | yes; weights on Google Drive (trained on RPLAN) | GPL-3.0 (weights follow RPLAN's research-only terms) |
| DiffPlanner (IEEE TVCG 2025), github.com/shidong-wang/DiffPlanner | outline + entrance | yes; trained model zip (RPLAN) | not stated |
| HouseDiffusion (CVPR 2023) | room graph | paper; code to find | — |

## Hardware
This laptop: NVIDIA RTX 3060 Laptop, 6 GB. Enough to fine-tune or train a small diffusion model on 80,000 plans
(slow: days, with a small batch). A bigger GPU (university or cloud) would make it hours.

## Recommended path
1. Download MSD (CC BY 4.0) and use all of Swiss Dwellings and ResPlan: about 80,000 apartments.
2. Convert them to the GSDiff / DiffPlanner graph format: outline, entrance, rooms, doors.
3. Train a boundary-constrained generator on the RTX 3060: input = the shop or flat outline, façade and entrance;
   output = rooms and doors.
4. Every generated plan goes through NOMAD's stretch, rules, daylight and furniture checks; only passing plans are shown.
5. In parallel, request RPLAN and LIFULL (IAAC counts as an academic institution) to train a second, larger model.
6. Measure on the same 40 real shops: legal homes, dead space, how real the plans look.

Sources: ResPlan https://github.com/m-agour/ResPlan ; MSD https://data.4tu.nl/datasets/e1d89cb5-6872-48fc-be63-aadd687ee6f9 ;
RPLAN terms as described in https://arxiv.org/pdf/2605.14117 ; LIFULL https://www.nii.ac.jp/dsc/idr/en/lifull/documents/notice.pdf ;
CubiCasa5K https://github.com/CubiCasa/CubiCasa5k , https://zenodo.org/records/2613548 ; 3D-FRONT https://arxiv.org/abs/2011.09127 ;
FloorPlanCAD https://huggingface.co/datasets/moinmiami/FloorPlanCAD ; GSDiff https://github.com/SizheHu/GSDiff ;
DiffPlanner https://github.com/shidong-wang/DiffPlanner ; HouseDiffusion https://openaccess.thecvf.com/content/CVPR2023/papers/Shabani_HouseDiffusion_Vector_Floorplan_Generation_via_a_Diffusion_Model_With_Discrete_CVPR_2023_paper.pdf
