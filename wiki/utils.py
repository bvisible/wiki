import frappe
from frappe.core.doctype.file.utils import get_content_hash


def get_tailwindcss_hash():
	tailwindcss_path = frappe.get_app_path("wiki", "public/css/tailwind.css")
	content = open(tailwindcss_path).read()
	return get_content_hash(content)


def check_app_permission():
	"""Check if user has permission to access the app (for showing the app on app screen)"""

	if frappe.session.user == "Administrator":
		return True

	roles = frappe.get_roles()
	if "Wiki Manager" in roles:
		return True

	return False


def add_wiki_user_role(doc, event=None):
	# Wiki User role has desk_access=1, which would convert a Website User
	# into a System User (see frappe.core.doctype.user.user.set_system_user).
	# Only grant this role to actual desk users — website users browsing the
	# public wiki do not need it.
	if doc.user_type != "System User":
		return
	doc.add_roles("Wiki User")
