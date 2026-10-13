##! Baseline OT detections for the lab.
##!
##! Two behavioral checks, not signatures - Modbus has no authentication
##! field to key a signature on, so "who did it" and "how fast" are what
##! separates the HMI's traffic from the attacker's.
##!
##! 1. Any Modbus WRITE from a source other than the known HMI/engineering
##!    station is a T0855 (Unauthorized Command Message) candidate.
##! 2. A burst of requests from one source above a threshold, in a short
##!    window, is a T0814 (Denial of Service) candidate.

@load base/frameworks/notice
@load base/frameworks/sumstats

module OTLab;

export {
	redef enum Notice::Type += {
		Unauthorized_Modbus_Write,   # write from a non-engineering source
		Modbus_Request_Flood,        # too many requests in too little time
	};

	# Set this to your HMI/poller's address. Traffic from any other
	# source issuing a Modbus write trips Unauthorized_Modbus_Write.
	const known_engineering_hosts: set[addr] = { 172.20.0.11 } &redef;

	# Requests-per-source in the SumStats window before it is a flood.
	const flood_threshold: double = 100.0 &redef;
	const flood_window: interval = 5sec &redef;
}

# --- 1. Unauthorized write detection -----------------------------------

event modbus_write_single_coil_request(c: connection, headers: ModbusHeaders,
                                        address: count, value: bool)
	{
	local src = c$id$orig_h;
	if ( src !in known_engineering_hosts )
		NOTICE([$note=Unauthorized_Modbus_Write,
		        $msg=fmt("Coil write from unexpected source %s: addr=%d value=%s",
		                 src, address, value),
		        $conn=c, $identifier=cat(src)]);
	}

event modbus_write_single_register_request(c: connection, headers: ModbusHeaders,
                                            address: count, value: count)
	{
	local src = c$id$orig_h;
	if ( src !in known_engineering_hosts )
		NOTICE([$note=Unauthorized_Modbus_Write,
		        $msg=fmt("Register write from unexpected source %s: addr=%d value=%d",
		                 src, address, value),
		        $conn=c, $identifier=cat(src)]);
	}

# --- 2. Request-rate flood detection ------------------------------------

event modbus_message(c: connection, headers: ModbusHeaders, is_orig: bool)
	{
	if ( ! is_orig )
		return;
	SumStats::observe("otlab.modbus.requests",
	                   SumStats::Key($host=c$id$orig_h),
	                   SumStats::Observation($num=1));
	}

event zeek_init()
	{
	local r1: SumStats::Reducer = [$stream="otlab.modbus.requests", $apply=set(SumStats::SUM)];
	SumStats::create([$name="otlab-modbus-flood",
	                   $epoch=flood_window,
	                   $reducers=set(r1),
	                   $threshold=flood_threshold,
	                   $threshold_val(key: SumStats::Key, result: SumStats::Result): double =
	                       {
	                       return result["otlab.modbus.requests"]$sum;
	                       },
	                   $threshold_crossed(key: SumStats::Key, result: SumStats::Result) =
	                       {
	                       NOTICE([$note=Modbus_Request_Flood,
	                               $msg=fmt("%s sent %.0f Modbus requests in %s",
	                                        key$host, result["otlab.modbus.requests"]$sum,
	                                        flood_window),
	                               $identifier=cat(key$host)]);
	                       }]);
	}
