async function api(path, opts) {
  const res = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts));
  return res.json();
}

async function addEmployee() {
  const name = document.getElementById("empName").value.trim();
  if (!name) return;
  await api("/api/employees", { method: "POST", body: JSON.stringify({ name }) });
  document.getElementById("empName").value = "";
  refresh();
}

async function seedTickets() {
  const count = parseInt(document.getElementById("seedCount").value, 10) || 20;
  await api("/api/tickets/seed", { method: "POST", body: JSON.stringify({ count }) });
  refresh();
}

async function requestTicket(employeeId) {
  await api(`/api/employees/${employeeId}/request-ticket`, { method: "POST", body: "{}" });
  refresh();
}

async function completeTicket(employeeId, ticketId) {
  await api(`/api/tickets/${ticketId}/complete`, { method: "POST", body: JSON.stringify({ employee_id: employeeId }) });
  refresh();
}

async function simulateConcurrency() {
  const employees = await api("/api/employees");
  const idle = employees.filter(e => e.status === "IDLE").slice(0, 20);
  const out = document.getElementById("simResult");
  if (idle.length < 2) {
    out.textContent = "Add a few idle employees first (at least 2, ideally 10+) to see it in action.";
    return;
  }
  out.textContent = `Firing ${idle.length} simultaneous requests...`;

  const results = await Promise.all(
    idle.map(e => api(`/api/employees/${e.id}/request-ticket`, { method: "POST", body: "{}" }))
  );

  const ticketIds = results.filter(r => r.id).map(r => r.id);
  const unique = new Set(ticketIds);
  const dupes = ticketIds.length - unique.size;

  out.textContent =
    `${idle.length} employees requested at once\n` +
    `${ticketIds.length} tickets were handed out\n` +
    `${unique.size} unique ticket IDs among them\n` +
    (dupes === 0 ? "✓ no duplicate assignments" : `✗ ${dupes} DUPLICATE assignment(s) detected!`);

  refresh();
}

async function refresh() {
  const [employees, tickets, stats] = await Promise.all([
    api("/api/employees"),
    api("/api/tickets"),
    api("/api/stats"),
  ]);

  document.getElementById("stats").innerHTML = `
    <div class="card"><div class="num">${stats.employees}</div><div class="lbl">Employees</div></div>
    <div class="card"><div class="num">${stats.tickets_pending}</div><div class="lbl">Pending</div></div>
    <div class="card"><div class="num">${stats.tickets_assigned}</div><div class="lbl">Assigned</div></div>
    <div class="card"><div class="num">${stats.tickets_completed}</div><div class="lbl">Completed</div></div>
  `;

  const empBody = document.querySelector("#empTable tbody");
  empBody.innerHTML = employees.map(e => `
    <tr>
      <td>${e.id}</td>
      <td>${e.name}</td>
      <td><span class="badge ${e.status}">${e.status}</span></td>
      <td>${e.current_ticket_id ?? "—"}</td>
      <td>
        ${e.status === "IDLE"
          ? `<button class="mini-btn" onclick="requestTicket(${e.id})">Request ticket</button>`
          : `<button class="mini-btn" onclick="completeTicket(${e.id}, ${e.current_ticket_id})">Complete</button>`}
      </td>
    </tr>
  `).join("");

  const tixBody = document.querySelector("#ticketTable tbody");
  tixBody.innerHTML = tickets.slice(-100).reverse().map(t => `
    <tr>
      <td>${t.id}</td>
      <td>${t.title}</td>
      <td><span class="badge ${t.status}">${t.status}</span></td>
      <td>${t.assigned_to ?? "—"}</td>
    </tr>
  `).join("");
}

refresh();
setInterval(refresh, 4000);
