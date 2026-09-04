// Copyright (c) 2023, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on("Wiki Space", {
  refresh(frm) {
    frm.add_web_link(`/${frm.doc.route}`, __("See on website"));

    frm.add_custom_button(__("Clone Wiki Space"), () => {
      frappe.prompt(
        [
          {
            fieldname: "new_space_route",
            fieldtype: "Data",
            label: __("New Space Route"),
            reqd: 1,
            description: __("Enter the new base route (without leading slash)"),
          },
        ],
        (values) => {
          frm
            .call({
              method: "clone_wiki_space_in_background",
              args: { new_space_route: values.new_space_route },
              freeze: true,
              freeze_message: __("Starting clone..."),
            })
            .then(() => {
              frappe.msgprint(__("Cloning started in background."));
            });
        },
        __("Clone Wiki Space"),
        __("Start Cloning"),
      );
    });

    if (frm.doc.root_group) {
      frm.add_custom_button(__("Bulk Update Routes"), () => {
        const dialog = new frappe.ui.Dialog({
          title: __("Update Wiki Space Routes"),
          fields: [
            {
              fieldname: "current_route",
              fieldtype: "Data",
              label: __("Current Base Route"),
              default: frm.doc.route,
              read_only: 1,
            },
            {
              fieldname: "new_route",
              fieldtype: "Data",
              label: __("New Base Route"),
              reqd: 1,
              description: __("Enter the new base route (without leading slash)"),
            },
          ],
          primary_action_label: __("Update Routes"),
          primary_action: (values) => {
            dialog.hide();
            frm.call({
              doc: frm.doc,
              method: "update_routes",
              args: { new_route: values.new_route },
              freeze: true,
              freeze_message: __("Updating routes..."),
            }).then((r) => {
              if (r.message) {
                frappe.msgprint({
                  title: __("Routes Updated"),
                  message: __("{0} documents updated successfully", [
                    r.message.updated_count,
                  ]),
                  indicator: "green",
                });
                frm.reload_doc();
              }
            });
          },
        });
        dialog.show();
      });
    }

    if ((frm.doc.wiki_sidebars || []).length) {
      frm.add_custom_button(__("Migrate to Version 3"), () => {
      frappe.confirm(
        __("This will sync the sidebar into tree-based Wiki Documents. Continue?"),
        () => {
          frm.call("migrate_to_v3").then(() => {
            frappe.msgprint(__("Migration completed successfully."));
            frm.reload_doc();
          });
        }
      );
    });
    }
  },

  onload_post_render: function (frm) {
    frm.trigger("set_parent_label_options");
  },

  set_parent_label_options: function (frm) {
    frm.fields_dict.navbar_items.grid.update_docfield_property(
      "parent_label",
      "options",
      frm.events.get_parent_options(frm, "navbar_items"),
    );
  },

  get_parent_options: function (frm, table_field) {
    var items = frm.doc[table_field] || [];
    var main_items = [""];
    for (var i in items) {
      var d = items[i];
      if (!d.url && d.label) {
        main_items.push(d.label);
      }
    }
    return main_items.join("\n");
  },
});

//// Neoffice — added handlers (no upstream equivalent). The Wiki Sidebars grid
//// shows Published and Allow Guest for each page (two Custom-Field-shaped
//// additions to Wiki Group Item, see NEOFFICE_FORK_MARKERS.md); ticking a box
//// in the grid writes the value onto the linked Wiki Page, so an admin can
//// publish or open a whole space from one screen instead of opening every
//// page. The child row itself only fetch_from's the value.
frappe.ui.form.on("Wiki Group Item", {
  published: function (frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (row.wiki_page) {
      frappe.call({
        method: "frappe.client.set_value",
        args: { doctype: "Wiki Page", name: row.wiki_page, fieldname: "published", value: row.published },
        callback: function () {
          frappe.show_alert({ message: __("Wiki Page updated"), indicator: "green" });
        },
      });
    }
  },
  allow_guest: function (frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (row.wiki_page) {
      frappe.call({
        method: "frappe.client.set_value",
        args: { doctype: "Wiki Page", name: row.wiki_page, fieldname: "allow_guest", value: row.allow_guest },
        callback: function () {
          frappe.show_alert({ message: __("Wiki Page updated"), indicator: "green" });
        },
      });
    }
  },
});

frappe.ui.form.on("Top Bar Item", {
  navbar_delete(frm) {
    frm.events.set_parent_label_options(frm);
  },

  navbar_add(frm, cdt, cdn) {
    frm.events.set_parent_label_options(frm);
  },

  parent_label: function (frm, doctype, name) {
    frm.events.set_parent_label_options(frm);
  },

  url: function (frm, doctype, name) {
    frm.events.set_parent_label_options(frm);
  },

  label: function (frm, doctype, name) {
    frm.events.set_parent_label_options(frm);
  },
});
