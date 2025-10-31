
from session_data import *
from visualize import *

session_dir = Path("../data/2025-10-30/session_141256")
session = SessionData.from_directory(session_dir)
session.load_all_router_batches()
print(session.summary())

plot_csi_phase_data(session)
plot_gps_trajectory(session)
plot_temporal_analysis(session)
# plot_animation_of_beamformer(session)

