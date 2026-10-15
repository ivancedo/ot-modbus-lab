@load base/frameworks/notice

module OTLab;

export {
	redef enum Notice::Type += { Rogue_Master_Write };

	# Authorized MODBUS hosts with write permissions
	const known_engineering_hosts: set[addr] = { 172.20.0.11 } &redef;
}

event modbus_write_single_coil_request(c: connection, headers: ModbusHeaders,
        address: count, value: bool)
	{
	local src = c$id$orig_h;
	if ( src !in known_engineering_hosts )
		NOTICE([$note=Rogue_Master_Write,
		        $msg=fmt("Rogue master: coil write from %s addr=%d value=%s",
		                 src, address, value),
		        $src=src,
		        $conn=c,
		        $identifier=cat(src, "coil")]);
	}

event modbus_write_single_register_request(c: connection, headers: ModbusHeaders,
        address: count, value: count)
	{
	local src = c$id$orig_h;
	if ( src !in known_engineering_hosts )
		NOTICE([$note=Rogue_Master_Write,
		        $msg=fmt("Rogue master: register write from %s addr=%d value=%d",
		                 src, address, value),
		        $src=src,
		        $conn=c,
		        $identifier=cat(src, "reg")]);
	}