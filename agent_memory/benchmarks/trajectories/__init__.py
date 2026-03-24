"""
Benchmark trajectory registry.
"""

from benchmarks.trajectories.family_a import ALL_TRAJECTORIES as FAMILY_A_TRAJECTORIES
from benchmarks.trajectories.family_b import ALL_TRAJECTORIES as FAMILY_B_TRAJECTORIES
from benchmarks.trajectories.family_c import ALL_TRAJECTORIES as FAMILY_C_TRAJECTORIES
from benchmarks.trajectories.family_d import ALL_TRAJECTORIES as FAMILY_D_TRAJECTORIES
from benchmarks.trajectories.family_e import ALL_TRAJECTORIES as FAMILY_E_TRAJECTORIES
from benchmarks.trajectories.family_f import ALL_TRAJECTORIES as FAMILY_F_TRAJECTORIES


ALL_TRAJECTORIES = (
    FAMILY_A_TRAJECTORIES
    + FAMILY_B_TRAJECTORIES
    + FAMILY_C_TRAJECTORIES
    + FAMILY_D_TRAJECTORIES
    + FAMILY_E_TRAJECTORIES
    + FAMILY_F_TRAJECTORIES
)

