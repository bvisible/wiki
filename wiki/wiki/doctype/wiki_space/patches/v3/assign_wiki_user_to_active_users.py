import frappe


def execute():
	#//// Neoffice — restrict to desk users. Upstream granted "Wiki User" to EVERY
	#//// enabled account, exceptions swallowed. The role is auto-created with
	#//// desk_access=1, so frappe promotes each holder to System User and every portal
	#//// account starts consuming a paid licence seat (WI-00353). This patch is already
	#//// logged as run across the fleet, so the filter only protects fresh installs and
	#//// restored sites — which is exactly where it would still fire.
	active_users = frappe.db.get_all(
		"User", filters={"enabled": 1, "user_type": "System User"}, pluck="name"
	)
	for user in active_users:
		try:
			frappe.get_doc("User", user).add_roles("Wiki User")
			frappe.db.commit()
		except Exception:
			pass
