@load base/frameworks/notice

module OTLab;

export {
	redef enum Notice::Type += { Modbus_Recon };

	const master: addr = 172.20.0.20 &redef;
}

event modbus_read_input_registers_request(c: connection, headers: ModbusHeaders,
    start_address: count, quantity: count)
	{
	if ( c$id$orig_h == master )
		return;

	NOTICE([$note=Modbus_Recon,
	        $msg=fmt("Modbus recon: %s read %d register(s) from %s",
	                 c$id$orig_h, quantity, c$id$resp_h),
	        $src=c$id$orig_h,
	        $conn=c,
	        $identifier=cat(c$id$orig_h, c$id$resp_h)]);
	}
