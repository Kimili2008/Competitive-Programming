# Stress test results

Status counts: {'no_solution': 21, 'valid': 5}

Hard generated cases have no proven shortest reference. Proxy scores use the stored witness length.

| Case | Size | Pearls | Status | Seconds | Length | Witness |
|---|---|---:|---|---:|---:|---:|
| [random_01_sparse](random_01_sparse.in) | 50x50 | 54 | no_solution | 9.050 | - | 952 |
| [random_01_medium](random_01_medium.in) | 50x50 | 204 | no_solution | 9.054 | - | 952 |
| [random_01_dense](random_01_dense.in) | 50x50 | 475 | no_solution | 9.051 | - | 952 |
| [random_01_full](random_01_full.in) | 50x50 | 680 | no_solution | 9.056 | - | 952 |
| [random_02_sparse](random_02_sparse.in) | 50x50 | 55 | no_solution | 9.053 | - | 952 |
| [random_02_medium](random_02_medium.in) | 50x50 | 209 | no_solution | 9.060 | - | 952 |
| [random_02_dense](random_02_dense.in) | 50x50 | 489 | no_solution | 9.059 | - | 952 |
| [random_02_full](random_02_full.in) | 50x50 | 699 | no_solution | 9.048 | - | 952 |
| [random_03_sparse](random_03_sparse.in) | 50x50 | 33 | no_solution | 9.064 | - | 660 |
| [random_03_medium](random_03_medium.in) | 50x50 | 124 | no_solution | 9.078 | - | 660 |
| [random_03_dense](random_03_dense.in) | 50x50 | 289 | no_solution | 9.085 | - | 660 |
| [random_03_full](random_03_full.in) | 50x50 | 414 | no_solution | 9.507 | - | 660 |
| [random_04_sparse](random_04_sparse.in) | 48x50 | 54 | no_solution | 9.264 | - | 912 |
| [random_04_medium](random_04_medium.in) | 48x50 | 204 | no_solution | 9.073 | - | 912 |
| [random_04_dense](random_04_dense.in) | 48x50 | 478 | no_solution | 9.058 | - | 912 |
| [random_04_full](random_04_full.in) | 48x50 | 683 | no_solution | 9.064 | - | 912 |
| [tight_05_sparse](tight_05_sparse.in) | 50x50 | 54 | no_solution | 9.054 | - | 1900 |
| [tight_05_medium](tight_05_medium.in) | 50x50 | 203 | no_solution | 9.062 | - | 1900 |
| [tight_05_dense](tight_05_dense.in) | 50x50 | 474 | no_solution | 9.081 | - | 1900 |
| [tight_05_full](tight_05_full.in) | 50x50 | 678 | no_solution | 9.058 | - | 1900 |
| [snake_06_sparse](snake_06_sparse.in) | 50x40 | 9 | valid | 0.124 | 276 | 960 |
| [snake_06_medium](snake_06_medium.in) | 50x40 | 36 | valid | 2.432 | 474 | 960 |
| [snake_06_dense](snake_06_dense.in) | 50x40 | 84 | no_solution | 9.051 | - | 960 |
| [snake_06_full](snake_06_full.in) | 50x40 | 121 | valid | 0.112 | 960 | 960 |
| [control_boundary](control_boundary.in) | 50x50 | 5 | valid | 0.055 | 196 | 196 |
| [control_interior](control_interior.in) | 50x50 | 5 | valid | 0.036 | 128 | 128 |

[Full inputs, actual outputs and witnesses](all_inputs_outputs.md)
