
from session_data import *
from visualize import *

session_dir = Path("../data/2025-11-04/session_172933")
auto_clean_session(session_dir)

session = SessionData.from_directory(session_dir)
session.load_all_router_batches()
print(session.summary())

plot_csi_phase_data(session)
# plot_gps_trajectory(session)
# plot_temporal_analysis(session)
# plot_animation_of_beamformer(session, plot_image=True)

