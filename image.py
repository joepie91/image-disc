import subprocess, sys, os, random, string, re, time

drive = sys.argv[1]
target_path = sys.argv[2]

if sys.argv[3] == "--ddrescue":
	forced_ddrescue = True
else:
	forced_ddrescue = False

def mount_drive(drive):
	output = subprocess.check_output(["udisksctl", "mount", "-b", drive])
	# urgh, regex to extract the mountpath...
	match = re.search("Mounted [^ ]+ at (.+)\.$", output, re.MULTILINE)
	if match is None:
		raise Exception("Drive failed to mount.")
	else:
		return match.group(1)

def unmount_drive(drive):
	retcode = subprocess.call(["udisksctl", "unmount", "-b", drive])
	if retcode != 0:
		raise Exception("Drive failed to unmount.")

def get_disc_info(drive):
	return [line.strip() for line in subprocess.check_output(["udevadm", "info", "-q", "env", "-n", drive]).splitlines()]

def format_bytes(inp):
	amount, unit = inp.rsplit(" ", 1)
	map_ = {
		"B": 1,
		"KB": 1024,
		"MB": 1024 * 1024,
		"GB": 1024 * 1024 * 1024
	}
	return int(amount) * map_[unit.upper()]

while True:
	name = raw_input("## What is the name of the next disc? ")

	# Try to unmount the drive, just in case it was auto-mounted
	try:
		unmount_drive(drive)
	except:
		# Doesn't matter, wasn't mounted to begin with.
		pass

	media_type = "unknown"

	print "## Waiting for media to be recognized... Please close the tray if it is still opened."

	while True:
		# This is a loop to wait until the disc is recognized...
		disc_info = get_disc_info(drive)

		if "ID_CDROM_MEDIA=1" in disc_info:
			break # Disc was recognized, end loop

		time.sleep(0.5)

	# Now determine the media type.
	if "ID_CDROM_MEDIA_CD=1" in disc_info or "ID_CDROM_MEDIA_CD_R=1" in disc_info:
		# Some kind of CD.
		data_tracks = 0
		audio_tracks = 0
		total_tracks = 0

		for line in disc_info:
			key, value = line.split("=", 1)

			if key == "ID_CDROM_MEDIA_TRACK_COUNT_AUDIO":
				audio_tracks = int(value)
			elif key == "ID_CDROM_MEDIA_TRACK_COUNT_DATA":
				data_tracks = int(value)
			elif key == "ID_CDROM_MEDIA_TRACK_COUNT":
				total_tracks = int(value)

		if total_tracks != (data_tracks + audio_tracks):
			print "## ERROR: Unrecognized tracks found on CD! Please report this as a bug."
			continue # Abort imaging cycle

		if data_tracks == 0 and audio_tracks > 0:
			media_type = "cd-audio"
		elif data_tracks > 0 and audio_tracks == 0:
			media_type = "cd-data"
		elif data_tracks > 0 and audio_tracks > 0:
			media_type = "cd-mixed"
		else:
			media_type = "cd-blank"
	elif "ID_CDROM_MEDIA_DVD=1" in disc_info:
		# We cannot distinguish between a Video-DVD and a DVD-ROM from the udev data alone.
		try:
			mount_path = mount_drive(drive)
		except subprocess.CalledProcessError, e:
			# Could not mount; try to unmount and mount again.
			print "## WARNING: Drive already mounted; re-mounting..."
			# Wait for a bit first, to let the auto-mount complete...
			time.sleep(1)
			unmount_drive(drive)
			mount_path = mount_drive(drive)

		if os.path.exists(os.path.join(mount_path, "VIDEO_TS")):
			media_type = "dvd-video"
		elif os.path.exists(os.path.join(mount_path, "AUDIO_TS")):
			media_type = "dvd-audio"
		else:
			media_type = "dvd-data"
		# Apparently some discs will not work correctly, if we don't wait before unmounting...
		time.sleep(1)
		unmount_drive(drive)

	# Now we'll do something, depending on the media type.
	if media_type == "unknown":
		print "## ERROR: Failed to determine media type for disc."
		continue # abort

	if media_type == "cd-blank": # TODO: Figure out blank-ness of a DVD.
		print "## ERROR: Cannot image blank disc!"
		continue # abort

	type_map = {
		"cd-audio": "Audio CD",
		"cd-data": "Data CD(-ROM)",
		"cd-mixed": "CD(-ROM) with non-data (eg. audio) tracks",
		"dvd-video": "Video DVD",
		"dvd-audio": "Audio DVD",
		"dvd-data": "Data DVD-ROM"
	}

	print "## Disc detected as %s" % type_map[media_type]

	if media_type in ("cd-data", "cd-mixed") and not forced_ddrescue:
		bin_path = os.path.join(target_path, "%s.bin" % name)
		cue_path = os.path.join(target_path, "%s.cue" % name)
		tmp_path = "/tmp/image-%s" % ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(8))

		print "## Starting imaging process..."

		tries = 0
		success = False

		# TODO: Read output to scan for "Device or resource busy"
		while True:
			try:
				unmount_drive(drive)
			except:
				# Doesn't matter, wasn't mounted to begin with.
				pass

			retcode = subprocess.call([
				"cdrdao", "read-cd",
				"--device", drive,
				"--read-raw",
				"--datafile", bin_path,
				"-v", "2",
				tmp_path
			])

			if retcode != 0:
				if tries < 2:
					print "## WARNING: Imaging failed, retrying in a second..."
					time.sleep(1)
					tries += 1
					continue # Retry
				else:
					print "## ERROR: IMAGING FAILED."
					success = False
					break
			else:
				print "## Imaging finished successfully."
				success = True
				break

		if success == False:
			continue # Abort

		print "## Generating cuesheet..."

		retcode = subprocess.call([
			"toc2cue",
			tmp_path,
			cue_path
		])

		if retcode != 0:
			print "## ERROR: CUESHEET CREATION FAILED."
			continue
		else:
			print "## Cuesheet creation finished successfully."

		if media_type == "cd-mixed":
			print "## WARNING: The disc contains audio tracks as well. You may want to consider using an Audio CD ripper for those."
	elif media_type == "cd-audio":
		print "## ERROR: Cannot currently image Audio CDs. Please use an Audio CD ripper instead."
	elif media_type in ("dvd-audio", "dvd-video", "dvd-data") or forced_ddrescue:
		# Create an ISO, that should be sufficient... use ddrescue by default.
		iso_path = os.path.join(target_path, "%s.iso" % name)
		log_path = os.path.join(target_path, "%s.ddrescuelog" % name)

		if media_type == "dvd-video":
			# We hook the stdout/stderr here, to detect large amounts of read errors for video-DVDs,
			# which is a likely indicator of ARccOS protection.
			# FIXME: Currently -completely- broken! Needs fixing ASAP.
			arccos = False
			proc = subprocess.Popen(["ddrescue", "-A", "-M", "-r", "20", "-b", "2048", drive, iso_path, log_path], stderr=subprocess.STDOUT, stdout=subprocess.PIPE, bufsize=1)

			while proc.poll() is None:
				line = proc.stdout.readline()
				sys.stdout.write(line)
				match = re.match("rescued:\s*([0-9]+ [A-Z]+),\s*errsize:\s*([0-9]+ [A-Z]+)", line)
				if match is not None and arccos == False:
					# Status line...
					rescued_bytes = format_bytes(match.group(1))
					error_bytes = format_bytes(match.group(2))
					if error_bytes > rescued_bytes and error_bytes > (1024 * 1024 * 10) and rescued_bytes > (1024 * 1024 * 10):
						# Only trigger if there's more read errors than read successes, and both
						# values exceed 10MB.
						print "## WARNING: Large amount of read errors detected, likely ARccOS-protected. Restarting with different parameters..."
						arccos = True
						# TODO: Figure out working parameters...
						#break

			if arccos == False:
				proc.communicate()
				retcode = proc.returncode
			else:
				os.remove(iso_path)
				os.remove(log_path)
				# TODO: Run with proper params...
		else:
			retcode = subprocess.call(["ddrescue", "-A", "-M", "-r", "20", "-b", "2048", drive, iso_path, log_path])

		if retcode in (1, 3):
			print "## ERROR: An error occurred in ddrescue."
			continue
		elif retcode == 2:
			print "## WARNING: ddrescue indicates corruption, image may have failed."
			# arccos bypass:
			# sdparm --set=RRC=0 /dev/sr0

	# It might've been automounted by something again...
	subprocess.call(["udisksctl", "unmount", "-b", drive])

	# Eject the drive
	subprocess.call(["eject", drive])
