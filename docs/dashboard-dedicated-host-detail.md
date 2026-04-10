# Dedicated Host Detail Dashboard — Build Guide

**Platform:** VMware Aria Operations 8.18.6 Enterprise
**Management Pack:** Azure Government Cloud (AzureGovAdapter)
**Purpose:** Select an Azure Dedicated Host and view its cost, capacity, hosted VMs, and attached disks in a single pane.

---

## Prerequisites

- The Azure Government Cloud management pack is installed and collecting data.
- Your Aria Ops user account has the **Content Admin** or **Administrator** role.
- At least one `azure_dedicated_host` object is reporting metrics.

---

## 1. Create the Dashboard

1. In the left navigation menu, click **Visualize > Dashboards**.
2. Click the **Create** button (top-left toolbar). A new blank dashboard canvas opens in the Dashboard Editor.
3. In the **Dashboard Configuration** panel on the right:
   - **Name:** `Dedicated Host Detail`
   - **Description:** `Shows cost, capacity, VMs, and disks for a selected Azure Dedicated Host.`
   - **Share with Everyone:** Check this box if other admins need access.
4. Leave the dashboard in edit mode — you will add widgets next.

---

## 2. Widget 1 — Host Picker (Object List)

This widget lists all dedicated hosts and acts as the selection source that drives every other widget.

1. From the **Widget List** panel on the left side of the dashboard editor, drag an **Object List** widget onto the canvas.
2. Click the pencil icon on the widget title bar to open its configuration.
3. Set the following:
   - **Title:** `Dedicated Hosts`
   - **Refresh Interval:** 300 seconds (5 minutes)
4. Under the **Input Data** section:
   - Click **Objects** then click the **Add** button.
   - In the object picker dialog, expand the **Adapter Types** tree and select **AzureGovAdapter**.
   - Under AzureGovAdapter, select the object type **Azure Dedicated Host (azure_dedicated_host)**.
   - Click **Select All** (or pick specific hosts) and confirm.
5. Under **Output Data > Columns**, add the following properties so admins can identify hosts at a glance:
   - `host_name`
   - `sku_name`
   - `location`
   - `health_state`
   - `vm_count`
6. Click **Save** to close the widget configuration.

---

## 3. Widget 2 — Cost and Capacity Scoreboard

This widget displays key numeric values for the host selected in Widget 1.

1. Drag a **Scoreboard** widget onto the canvas to the right of Widget 1.
2. Open its configuration (pencil icon).
3. Set the following:
   - **Title:** `Cost & Capacity`
   - **Refresh Interval:** 300 seconds
4. Under **Input Data**, select **Self Provider** as **Off** (this widget will receive its object from Widget 1 via interaction).
5. Under **Output Data > Scoreboards**, add the following properties:
   - `hourly_rate` — Label: **Hourly Rate ($)**
   - `monthly_rate_estimate` — Label: **Monthly Estimate ($)**
   - `vm_count` — Label: **VMs Running**
   - `max_available_slots` — Label: **Max Available Slots**
   - `vm_size_distinct_count` — Label: **Distinct VM Sizes**
6. Set the **Layout** to a single row if you want a horizontal strip, or leave the default for a tile layout.
7. Click **Save**.

---

## 4. Widget 3 — Host Property List

This widget shows all detail properties for the selected host.

1. Drag a **Property List** widget onto the canvas below Widgets 1 and 2.
2. Open its configuration.
3. Set the following:
   - **Title:** `Host Properties`
   - **Refresh Interval:** 300 seconds
4. Under **Input Data**, make sure **Self Provider** is **Off** (it will be driven by Widget 1).
5. Under **Output Data > Properties**, add:
   - `host_name`
   - `sku_name`
   - `location`
   - `health_state`
   - `provisioning_state`
   - `host_group_name`
   - `resource_group`
   - `vm_size_summary`
   - `vm_disk_skus`
   - `allocatable_vm_summary`
6. Click **Save**.

---

## 5. Widget 4 — Object Relationship (Hierarchy Drill-Down)

This widget renders the parent-child tree so admins can visualize the Host Group > Dedicated Host > VM > Disk chain.

1. Drag an **Object Relationship** widget onto the canvas next to the Property List.
2. Open its configuration.
3. Set the following:
   - **Title:** `Resource Hierarchy`
   - **Refresh Interval:** 300 seconds
4. Under **Input Data**, set **Self Provider** to **Off**.
5. Under **Configuration**:
   - **Relationship depth — Parents:** `1` (shows the Host Group above the selected host)
   - **Relationship depth — Children:** `2` (shows VMs and their disks below the host)
6. Click **Save**.

---

## 6. Widget 5 — VMs on Selected Host (Object List)

This widget lists the virtual machines running on the host selected in Widget 1.

1. Drag another **Object List** widget onto the canvas below the Scoreboard.
2. Open its configuration.
3. Set the following:
   - **Title:** `Virtual Machines on Host`
   - **Refresh Interval:** 300 seconds
4. Under **Input Data**, set **Self Provider** to **Off** (driven by Widget 1).
5. Under **Input Transformation > Relationship**:
   - Set **Relationship Type** to **Children**.
   - Filter the child type to **Azure Virtual Machine (azure_virtual_machine)**.
   This tells the widget to show only child VMs of whatever host is selected.
6. Under **Output Data > Columns**, add:
   - `vm_name`
   - `vm_size`
   - `power_state`
   - `os_type`
   - `os_disk_storage_type`
   - `os_disk_size_gb`
   - `data_disk_count`
7. Click **Save**.

---

## 7. Widget 6 (Optional) — Disks on Selected VM (Object List)

This widget shows disk details for the VM selected in Widget 5.

1. Drag a third **Object List** widget onto the canvas below or beside Widget 5.
2. Open its configuration.
3. Set the following:
   - **Title:** `Disks on VM`
   - **Refresh Interval:** 300 seconds
4. Under **Input Data**, set **Self Provider** to **Off** (driven by Widget 5).
5. Under **Input Transformation > Relationship**:
   - Set **Relationship Type** to **Children**.
   - Filter the child type to **Azure Disk (azure_disk)**.
6. Under **Output Data > Columns**, add:
   - `disk_name`
   - `sku_name`
   - `sku_tier`
   - `disk_size_gb`
   - `disk_iops_read_write`
   - `disk_state`
   - `attached_vm_name`
7. Click **Save**.

---

## 8. Configure Widget Interactions

Widget interactions tell Aria Ops to pass the selected object from one widget to another. Without this step the driven widgets stay empty.

### 8.1 — Widget 1 drives Widgets 2, 3, 4, and 5

1. While still in the dashboard editor, click the **Widget Interactions** button in the top toolbar (the icon looks like two connected nodes).
2. The interaction editor opens as a table. Each row is a **receiving** widget; each column is a potential **source** widget.
3. Find the row for **Cost & Capacity** (Widget 2). In the column for **Dedicated Hosts** (Widget 1), check the box or select **Dedicated Hosts** from the dropdown. This means Widget 2 receives its object from Widget 1.
4. Repeat for the rows:
   - **Host Properties** (Widget 3) — set source to **Dedicated Hosts** (Widget 1).
   - **Resource Hierarchy** (Widget 4) — set source to **Dedicated Hosts** (Widget 1).
   - **Virtual Machines on Host** (Widget 5) — set source to **Dedicated Hosts** (Widget 1).

### 8.2 — Widget 5 drives Widget 6

5. Find the row for **Disks on VM** (Widget 6). Set its source to **Virtual Machines on Host** (Widget 5).
6. Click **Apply Interactions** to save.

### Summary of interaction chain

```
Widget 1 (Dedicated Hosts)
   ├── drives Widget 2 (Cost & Capacity)
   ├── drives Widget 3 (Host Properties)
   ├── drives Widget 4 (Resource Hierarchy)
   └── drives Widget 5 (Virtual Machines on Host)
                          └── drives Widget 6 (Disks on VM)
```

---

## 9. Suggested Layout Arrangement

Arrange the widgets in a two-column grid. Resize by dragging widget edges in the dashboard editor.

```
+-------------------------------+-------------------------------+
|  Widget 1: Dedicated Hosts    |  Widget 2: Cost & Capacity    |
|  (Object List — tall, left)   |  (Scoreboard — top right)     |
|                               +-------------------------------+
|                               |  Widget 4: Resource Hierarchy |
|                               |  (Object Relationship)        |
+-------------------------------+-------------------------------+
|  Widget 3: Host Properties    |  Widget 5: VMs on Host        |
|  (Property List)              |  (Object List)                |
+-------------------------------+-------------------------------+
|                  Widget 6: Disks on VM (Object List)          |
|                  (full width, optional)                       |
+---------------------------------------------------------------+
```

**Tips:**

- Make Widget 1 tall enough to show 10-15 rows without scrolling, since it is the primary selector.
- The Scoreboard (Widget 2) works best as a short, wide strip.
- After arranging, click **Save** in the dashboard editor toolbar to finalize.

---

## 10. Verify the Dashboard

1. Exit the dashboard editor by clicking the **X** or **Close Editor** button.
2. Click on any host in Widget 1. Widgets 2 through 5 should update within a few seconds.
3. Click on a VM in Widget 5. Widget 6 should show the disks for that VM.
4. If a widget stays empty, re-open **Widget Interactions** and confirm the source-target mapping is correct.
5. If properties are missing, confirm the management pack collection is returning data for those property keys by checking **Environment > Object Browser > (select the object) > Properties**.
