@load base/frameworks/notice
@load base/frameworks/sumstats

module OTLab;

export {
	redef enum Notice::Type += {
		Unauthorized_Modbus_Write,
		Modbus_Request_Flood,
	};

	const known_engineering_hosts: set[addr] = { 172.20.0.11 } &redef;

	const flood_threshold: double = 100.0 &redef;
	const flood_window: interval = 5sec &redef;
}

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
