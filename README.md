Record:

channel (redundant)
user id (pii)
chat guid (needed for reply but not needed overall)
timestamp
content


Should add:
stream time/date/vod

event_*:
	if shutting_down:
		return

	call (append_msg)

append_msg:
	msg_queue.append(msg)

	slept = 0
	while not shutting_down and slept < recording_interval:
		await sleep(smol_interval)
		slept += smol_interval

	self.__record_msg()

interval:
	if len(msg_queue) == 0:
		return default_interval
	return average([msg_queue[i + 1].timestamp - msg_queue[i].timestamp for i in range(len(msg_queue) - 1)])

chat:
	slept = 0
	while not shutting_down and slept < interval:
		await sleep(smol_interval)
		slept += smol_interval

	if shutting_down:
		return

	msg = generate_msg()
	emit_msg(msg)
