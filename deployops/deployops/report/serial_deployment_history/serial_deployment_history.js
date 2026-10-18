frappe.query_reports["Serial Deployment History"] = {
	filters: [
		{
			fieldname: "serial_no",
			label: __("Serial No"),
			fieldtype: "Link",
			options: "Serial No",
			reqd: 1,
		},
	],
};
