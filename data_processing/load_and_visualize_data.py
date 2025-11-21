
from session_data import *
from visualize import *

session_dir = Path("../data/2025-11-20/session_135938")
auto_clean_session(session_dir)

session = SessionData.from_directory(session_dir)
session.load_all_router_batches()
print(session.summary())

plot_csi_phase_data(session, averaged=False)
# plot_animation_of_beamformer(session, plot_image=False, azimuth=True)


