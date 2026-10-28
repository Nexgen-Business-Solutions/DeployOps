// DeployOps Equipment Allocation (#14 / #38). Status and dates only change through these buttons.

frappe.ui.form.on("DeployOps Equipment Allocation", {
	setup(frm) {
		frm.set_query("source_name", () => ({
			query: "deployops.api.jobs.source_link_query",
			filters: { company: frm.doc.company },
		}));
		frm.set_query("serial_no", () => ({
			query: "deployops.api.allocations.in_stock_serial_query",
			filters: { company: frm.doc.company },
		}));
	},

	allocation_type(frm) {
		frm.set_value(
			"source_doctype",
			frm.doc.allocation_type === "Rental" ? "Subscription" : "Sales Order"
		);
	},

	refresh(frm) {
		if (frm.is_new()) {
			frm.set_df_property("source_doctype", "read_only", 1);
			return;
		}
		frappe.call({
			method: "deployops.api.allocations.get_allocation_actions",
			args: { allocation: frm.doc.name },
			callback(r) {
				const actions = r.message || [];
				if (actions.includes("return")) {
					frm.add_custom_button(
						__("Return Machine"),
						() => return_dialog(frm),
						__("Actions")
					);
				}
				if (actions.includes("swap")) {
					frm.add_custom_button(
						__("Swap Machine"),
						() => swap_dialog(frm),
						__("Actions")
					);
				}
				if (actions.includes("cancel")) {
					frm.add_custom_button(
						__("Cancel Reservation"),
						() => cancel_dialog(frm),
						__("Actions")
					);
				}
			},
		});
		frm.add_custom_button(__("Serial History"), () =>
			frappe.set_route("query-report", "Serial Deployment History", {
				serial_no: frm.doc.serial_no,
			})
		);
	},
});

function call_and_reload(frm, method, args) {
	frappe.call({
		method,
		args: { allocation: frm.doc.name, ...args },
		freeze: true,
		callback: (r) => {
			if (r.message && r.message !== frm.doc.status && r.message.startsWith("DO-ALLOC-")) {
				frappe.set_route("Form", frm.doctype, r.message);
			} else {
				frm.reload_doc();
			}
		},
	});
}

function return_dialog(frm) {
	frappe.prompt(
		[
			{
				fieldname: "returned_on",
				fieldtype: "Date",
				label: __("Returned On"),
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
			{
				fieldname: "condition",
				fieldtype: "Small Text",
				label: __("Condition on Return"),
				reqd: 1,
			},
		],
		(values) => call_and_reload(frm, "deployops.api.allocations.return_machine", values),
		__("Return Machine"),
		__("Return")
	);
}

function swap_dialog(frm) {
	frappe.prompt(
		[
			{
				fieldname: "new_serial_no",
				fieldtype: "Link",
				options: "Serial No",
				label: __("Replacement Serial No"),
				reqd: 1,
				get_query: () => ({
					query: "deployops.api.allocations.in_stock_serial_query",
					filters: { company: frm.doc.company },
				}),
			},
			{
				fieldname: "condition",
				fieldtype: "Small Text",
				label: __("Condition of the machine taken back"),
				reqd: 1,
			},
		],
		(values) => call_and_reload(frm, "deployops.api.allocations.swap_machine", values),
		__("Swap Machine"),
		__("Swap")
	);
}

function cancel_dialog(frm) {
	frappe.prompt(
		{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
		(values) => call_and_reload(frm, "deployops.api.allocations.cancel_reservation", values),
		__("Cancel Reservation"),
		__("Cancel Reservation")
	);
}
