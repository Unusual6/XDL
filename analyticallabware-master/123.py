from .AnalyticalLabware.devices.Agilent.hplc import HPLCController

# Ensure path exists
# Otherwise change the path in the macro file and restart the macro in chemstation
default_command_path = (
    "C:\\Users\\group\\Code\\analyticallabware\\AnalyticalLabware\\test"
)

hplc = HPLCController(comm_dir=default_command_path)

# Check the status
hplc.status()

# Prepare for running
hplc.preprun()

# Switch the method
# ".M" is appended to the method name by default
hplc.switch_method(method_name="my_method")

# Execute the method and save the data in the target folder
# Under experiment name
hplc.run_method(
    data_dir="path_to_target_folder", experiment_name="name_of_your_experiment"
)

# Switch all modules into standby mode
hplc.standby()

# Obtain the last measure spectrum and store it in self.spectra collection
# Channels A, B, C and D are read by default
hplc.get_spectrum()

# When spectra are loaded, use can access the collection by the channel name
# And perform basic processing and analysis operations
chrom = hplc.spectra["A"]  # Chromatogram at channel A of the detector
chrom.find_peaks()  # Find peaks
chrom.show_spectrum()  # Display the chromatogram
