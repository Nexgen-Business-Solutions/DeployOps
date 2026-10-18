// DeployOps Job (#18 / #39). The pickers use DeployOps' own server checks, because DeployOps
// roles have no direct permission on ERPNext source documents or Serial Nos.

frappe.ui.form.on("DeployOps Job", {
	setup(frm) {
		frm.set_query("source_name", () => ({
			query: "deployops.api.jobs.source_link_query",
			filters: { company: frm.doc.company },
		}));

		frm.set_query("serial_no", "devices", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				query: "deployops.api.jobs.serial_link_query",
				filters: {
					item_code: row.item_code,
					company: doc.company,
					job_type: doc.job_type,
					source_doctype: doc.source_doctype,
					source_name: doc.source_name,
				},
			};
		});

		// Technicians are Website Users, which Frappe's default User picker leaves out.
		frm.set_query("assigned_technician", () => ({
			query: "deployops.api.jobs.technician_link_query",
			filters: {
				item_codes: [
					...new Set((frm.doc.devices || []).map((d) => d.item_code).filter(Boolean)),
				],
			},
		}));
	},

	// Workflow buttons (#19): the server lists only the moves this user may make right now.
	refresh(frm) {
		if (frm.is_new()) return;

		frappe.call({
			method: "deployops.api.jobs.get_actions",
			args: { job: frm.doc.name },
			callback(r) {
				const { job = [], devices = {} } = r.message || {};
				for (const action of job) {
					frm.add_custom_button(
						action.label,
						() =>
							run_workflow(
								frm,
								"deployops.api.jobs.job_action",
								{ action: action.action },
								action
							),
						__("Actions")
					);
				}
				if (Object.keys(devices).length) {
					frm.add_custom_button(__("Update Machine"), () =>
						update_machine_dialog(frm, devices)
					);
				}
			},
		});
	},

	source_doctype(frm) {
		frm.set_value("source_name", null);
	},

	// Picking the source fills in customer, contact, site and the machines (with serials when
	// the source has them). The server decides which machines this user may see.
	source_name(frm) {
		if (!frm.is_new()) return;

		frm.clear_table("devices");
		frm.refresh_field("devices");
		if (!frm.doc.source_doctype || !frm.doc.source_name) return;

		frappe.call({
			method: "deployops.api.jobs.get_source_details",
			args: {
				source_doctype: frm.doc.source_doctype,
				source_name: frm.doc.source_name,
				company: frm.doc.company,
			},
			freeze: true,
			callback(r) {
				const details = r.message;
				if (!details) return;

				if (!frm.doc.company) frm.set_value("company", details.company);
				for (const field of [
					"customer",
					"customer_name",
					"contact",
					"contact_display",
					"address",
					"address_display",
				]) {
					frm.set_value(field, details[field]);
				}

				for (const device of details.devices) {
					frm.add_child("devices", { ...device, device_status: "Pending" });
				}
				frm.refresh_field("devices");
			},
		});
	},
});

function run_workflow(frm, method, args, action) {
	const call = (reason) =>
		frappe.call({
			method,
			args: { job: frm.doc.name, reason, ...args },
			freeze: true,
			callback: () => frm.reload_doc(),
		});

	if (action.reason_required) {
		frappe.prompt(
			{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
			(values) => call(values.reason),
			action.label,
			action.label
		);
	} else {
		frappe.confirm(__("{0}?", [action.label]), () => call());
	}
}

function update_machine_dialog(frm, devices) {
	const label = (row) =>
		row.serial_no
			? `${row.item_code} / ${row.serial_no}`
			: `${row.item_code} (row ${row.idx})`;
	const rows = frm.doc.devices.filter((row) => devices[row.name]);

	const dialog = new frappe.ui.Dialog({
		title: __("Update Machine"),
		fields: [
			{
				fieldname: "device",
				fieldtype: "Select",
				label: __("Machine"),
				reqd: 1,
				options: rows.map((row) => ({
					value: row.name,
					label: `${label(row)} — ${__(row.device_status)}`,
				})),
				onchange() {
					const actions = devices[dialog.get_value("device")] || [];
					dialog.set_df_property(
						"action",
						"options",
						actions.map((a) => ({ value: a.action, label: a.label }))
					);
					dialog.set_value("action", actions.length ? actions[0].action : null);
				},
			},
			{ fieldname: "action", fieldtype: "Select", label: __("Action"), reqd: 1 },
			{
				fieldname: "reason",
				fieldtype: "Small Text",
				label: __("Reason (required to block or cancel)"),
			},
		],
		primary_action_label: __("Apply"),
		primary_action(values) {
			frappe.call({
				method: "deployops.api.jobs.device_action",
				args: {
					job: frm.doc.name,
					device: values.device,
					action: values.action,
					reason: values.reason,
				},
				freeze: true,
				callback: () => {
					dialog.hide();
					frm.reload_doc();
				},
			});
		},
	});
	dialog.show();
	if (rows.length) {
		dialog.set_value("device", rows[0].name);
	}
}
