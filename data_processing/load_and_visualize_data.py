
from session_data import *
from visualize import *

session_dir = Path("../data/2026-02-08/session_121146")
auto_clean_session(session_dir)

session = SessionData.from_directory(session_dir)
session.load_all_router_batches()
print(session.summary())

# plot_csi_phase_data(session, averaged=False)
# plot_animation_of_beamformer(session, plot_image=False, azimuth=True, averaged=True)
# plot_ftm_timeseries(session, save_path=session.get_save_plot_path() / 'ftm_timeseries.png')
plot_csi_phase_data(session, save_path=session.get_save_plot_path() / 'csi_phase_data.png', averaged=True)

