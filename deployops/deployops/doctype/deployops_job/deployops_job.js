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
