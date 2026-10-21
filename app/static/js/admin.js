// Shaheen Public High School Loi Shalman - Principal Admin Controller

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initOverview();
  initStudents();
  initCards();
  initReports();
  initLeaves();
  initSettings();
  initAuth();
  loadStudents(); // Preload full students list in background for instant filtering
});

// --- Tab Management ---
function initTabs() {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      tabs.forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add('active');

      // Trigger loads on tab switch
      if (targetId === 'tab-students') loadStudents();
      if (targetId === 'tab-reports') loadReportsData();
      if (targetId === 'tab-leaves') loadLeaves();
    });
  });
}

function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('hidden');
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('hidden');
}
window.closeModal = closeModal;

// --- TAB 1: OVERVIEW & LIVE ATTENDANCE ---
let overviewRecords = [];

function initOverview() {
  const dateInput = document.getElementById('overview-date');
  const refreshBtn = document.getElementById('overview-refresh-btn');
  const classFilter = document.getElementById('overview-class-filter');
  const statusFilter = document.getElementById('overview-status-filter');
  const searchInput = document.getElementById('overview-search');
  const autoMarkBtn = document.getElementById('auto-mark-absentees-btn');

  loadOverviewData();

  if (dateInput) {
    dateInput.addEventListener('change', () => {
      updatePrintAndExportLinks();
      loadOverviewData();
    });
  }
  if (refreshBtn) refreshBtn.addEventListener('click', loadOverviewData);
  if (classFilter) classFilter.addEventListener('change', filterAndRenderOverviewTable);
  if (statusFilter) statusFilter.addEventListener('change', filterAndRenderOverviewTable);
  if (searchInput) searchInput.addEventListener('input', filterAndRenderOverviewTable);

  if (autoMarkBtn) {
    autoMarkBtn.addEventListener('click', async () => {
      const curDate = document.getElementById('overview-date').value;
      if (!confirm(`Are you sure you want to close attendance for ${curDate}? All unmarked students will be marked as Absent.`)) {
        return;
      }
      try {
        const res = await fetch(`/api/attendance/auto-mark-absentees?target_date=${curDate}`, { method: 'POST' });
        const data = await res.json();
        alert(`Attendance closed: ${data.marked_count} students marked as Absent/Leave.`);
        loadOverviewData();
      } catch (err) {
        alert('Error closing attendance: ' + err.message);
      }
    });
  }

  // Save manual correction
  const saveCorrBtn = document.getElementById('save-correction-btn');
  if (saveCorrBtn) {
    saveCorrBtn.addEventListener('click', async () => {
      const stuId = document.getElementById('corr-student-id').value;
      const dt = document.getElementById('corr-date').value;
      const status = document.getElementById('corr-status-select').value;
      const reason = document.getElementById('corr-reason').value;

      try {
        const res = await fetch('/api/attendance/manual-correct', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            student_id: parseInt(stuId),
            date: dt,
            new_status: status,
            reason: reason
          })
        });
        const data = await res.json();
        if (data.success) {
          closeModal('correction-modal');
          loadOverviewData();
        } else {
          alert('Correction failed: ' + data.message);
        }
      } catch (err) {
        alert('Network error saving correction');
      }
    });
  }

  // Delete / Remove attendance entry from modal
  const deleteCorrBtn = document.getElementById('delete-correction-btn');
  if (deleteCorrBtn) {
    deleteCorrBtn.addEventListener('click', async () => {
      const stuId = document.getElementById('corr-student-id').value;
      const dt = document.getElementById('corr-date').value;
      const name = document.getElementById('corr-student-name').textContent;

      if (!confirm(`Are you sure you want to completely remove this attendance record for ${name} on ${dt}?\n\nThis will reset the student back to Unmarked.`)) {
        return;
      }

      try {
        const res = await fetch('/api/attendance/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            student_id: parseInt(stuId),
            date: dt
          })
        });
        const data = await res.json();
        if (data.success) {
          closeModal('correction-modal');
          loadOverviewData();
          alert(data.message || 'Attendance entry removed successfully.');
        } else {
          alert('Delete failed: ' + (data.message || 'Error'));
        }
      } catch (err) {
        alert('Network error removing attendance record');
      }
    });
  }
}

function updatePrintAndExportLinks() {
  const dt = document.getElementById('overview-date').value;
  const cls = document.getElementById('overview-class-filter').value;
  const printBtn = document.getElementById('overview-print-btn');
  const exportBtn = document.getElementById('overview-export-excel-btn');

  if (printBtn) printBtn.href = `/print/report?date=${dt}&class_name=${cls}`;
  if (exportBtn) exportBtn.href = `/api/reports/export-excel?start_date=${dt}&end_date=${dt}&class_name=${cls}`;
}

async function loadOverviewData() {
  const dateVal = document.getElementById('overview-date').value;
  const classVal = document.getElementById('overview-class-filter').value;

  try {
    const res = await fetch(`/api/attendance/summary?date=${dateVal}&class_name=${classVal}`);
    if (!res.ok) throw new Error('Failed to load overview data');
    const data = await res.json();

    // Populate KPIs
    document.getElementById('kpi-total').textContent = data.total_students || 0;
    document.getElementById('kpi-present').textContent = data.present || 0;
    document.getElementById('kpi-rate').textContent = `${data.attendance_rate || 0}% attendance rate`;
    document.getElementById('kpi-late').textContent = data.late || 0;
    document.getElementById('kpi-absent').textContent = data.absent || 0;
    document.getElementById('kpi-leave').textContent = data.leave || 0;

    // Populate Class Progress Cards
    renderClassProgress(data.class_stats || []);

    // Cache records and render table
    overviewRecords = data.records || [];
    filterAndRenderOverviewTable();
  } catch (err) {
    console.error('Error loading overview:', err);
  }
}

function renderClassProgress(stats) {
  const container = document.getElementById('class-progress-grid');
  if (!container) return;

  if (!stats.length) {
    container.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">No class data available.</div>';
    return;
  }

  container.innerHTML = stats.map(s => {
    const attended = (s.present || 0) + (s.late || 0);
    const rate = s.total > 0 ? Math.round((attended / s.total) * 100) : 0;
    return `
      <div class="class-card">
        <div class="class-card-header">
          <span>Class ${s.class_name}</span>
          <span style="color: var(--primary);">${attended}/${s.total} (${rate}%)</span>
        </div>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" style="width: ${rate}%;"></div>
        </div>
        <div class="class-stats-row">
          <span>✅ ${s.present} Pres</span>
          <span>⚠️ ${s.late} Late</span>
          <span>❌ ${s.absent} Abs</span>
          <span>📅 ${s.leave} Leav</span>
        </div>
      </div>
    `;
  }).join('');
}

function filterAndRenderOverviewTable() {
  const tbody = document.getElementById('overview-table-body');
  if (!tbody) return;

  const classFilter = document.getElementById('overview-class-filter').value.toLowerCase();
  const statusFilter = document.getElementById('overview-status-filter').value;
  const searchVal = document.getElementById('overview-search').value.toLowerCase().trim();

  const filtered = overviewRecords.filter(r => {
    if (classFilter && r.class_name.toLowerCase() !== classFilter) return false;
    if (statusFilter && r.status !== statusFilter) return false;
    if (searchVal) {
      const match = (r.full_name || '').toLowerCase().includes(searchVal) ||
                    (r.roll_no || '').toLowerCase().includes(searchVal) ||
                    (r.student_code || '').toLowerCase().includes(searchVal) ||
                    (r.father_name || '').toLowerCase().includes(searchVal);
      if (!match) return false;
    }
    return true;
  });

  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 24px; color: var(--text-muted);">No attendance records found matching filters.</td></tr>';
    return;
  }

  const curDate = document.getElementById('overview-date').value;

  tbody.innerHTML = filtered.map(r => {
    const statusClass = `badge-${r.status.toLowerCase()}`;
    return `
      <tr>
        <td><code>${r.student_code}</code></td>
        <td><strong>${r.roll_no}</strong></td>
        <td><strong>${r.full_name}</strong></td>
        <td>${r.father_name || '-'}</td>
        <td><span style="color: var(--primary); font-weight: 600;">${r.class_name}</span></td>
        <td><span class="badge ${statusClass}">${r.status}</span></td>
        <td>${r.scan_time || '-'}</td>
        <td><small style="color: var(--text-muted);">${r.scan_method || '-'}</small></td>
        <td style="font-size: 11px; color: #64748b;">${r.notes || ''}</td>
        <td style="white-space: nowrap;">
          <button class="btn btn-secondary btn-sm" onclick="openCorrectionModal(${r.student_id}, '${escapeHtml(r.full_name)}', '${r.class_name}', '${curDate}', '${r.status}', '${escapeHtml(r.notes || '')}')" title="Edit status">
            ✏️ Edit
          </button>
          ${r.status !== 'Unmarked' ? `
          <button class="btn btn-danger btn-sm" onclick="removeAttendanceEntry(${r.student_id}, '${escapeHtml(r.full_name)}', '${curDate}')" title="Delete attendance record" style="margin-left: 4px; background: #dc2626; color: #fff;">
            🗑️ Remove
          </button>` : ''}
        </td>
      </tr>
    `;
  }).join('');
}

window.removeAttendanceEntry = async function(studentId, name, dateStr) {
  if (!confirm(`Are you sure you want to remove the attendance entry for ${name} on ${dateStr}?\n\nThis will reset the student back to Unmarked.`)) {
    return;
  }
  try {
    const res = await fetch('/api/attendance/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ student_id: studentId, date: dateStr })
    });
    const data = await res.json();
    if (data.success) {
      alert(data.message || `Attendance removed for ${name}`);
      loadOverviewData();
    } else {
      alert('Delete failed: ' + (data.message || 'Error'));
    }
  } catch (err) {
    alert('Network error while removing attendance entry');
  }
};

window.openCorrectionModal = function(studentId, name, className, dateStr, currentStatus, notes) {
  document.getElementById('corr-student-id').value = studentId;
  document.getElementById('corr-date').value = dateStr;
  document.getElementById('corr-student-name').textContent = name;
  document.getElementById('corr-meta').textContent = `Class: ${className} | Date: ${dateStr}`;
  document.getElementById('corr-status-select').value = (currentStatus === 'Unmarked' ? 'Present' : currentStatus);
  document.getElementById('corr-reason').value = notes;
  openModal('correction-modal');
};


// --- TAB 2: STUDENTS MANAGEMENT ---
let allStudentsMasterList = [];
let studentsList = [];

function initStudents() {
  const classFilter = document.getElementById('student-class-filter');
  const genderFilter = document.getElementById('student-gender-filter');
  const photoFilter = document.getElementById('student-photo-filter');
  const searchInput = document.getElementById('student-search-input');
  const addBtn = document.getElementById('add-student-btn');
  const bulkBtn = document.getElementById('bulk-upload-btn');

  // All 4 filters trigger instant 0ms client-side filtering over allStudentsMasterList
  if (classFilter) classFilter.addEventListener('change', renderStudentsTable);
  if (genderFilter) genderFilter.addEventListener('change', renderStudentsTable);
  if (photoFilter) photoFilter.addEventListener('change', renderStudentsTable);
  if (searchInput) searchInput.addEventListener('input', renderStudentsTable);

  if (addBtn) {
    addBtn.addEventListener('click', () => {
      document.getElementById('stu-id').value = '';
      document.getElementById('student-modal-title').textContent = 'Add New Student';
      document.getElementById('stu-name').value = '';
      document.getElementById('stu-father').value = '';
      document.getElementById('stu-roll').value = '';
      document.getElementById('stu-phone').value = '';
      document.getElementById('stu-address').value = 'Loi Shalman';
      openModal('student-modal');
    });
  }

  // Save student
  const saveStuBtn = document.getElementById('save-student-btn');
  if (saveStuBtn) {
    saveStuBtn.addEventListener('click', async () => {
      const id = document.getElementById('stu-id').value;
      const name = document.getElementById('stu-name').value.trim();
      const father = document.getElementById('stu-father').value.trim();
      const className = document.getElementById('stu-class').value;
      const roll = document.getElementById('stu-roll').value.trim();
      const phone = document.getElementById('stu-phone').value.trim();
      const gender = document.getElementById('stu-gender').value;
      const address = document.getElementById('stu-address').value.trim();

      if (!name || !roll) {
        alert('Please fill in Student Name and Roll Number.');
        return;
      }

      const payload = {
        full_name: name,
        father_name: father,
        class_name: className,
        roll_no: roll,
        parent_phone: phone,
        gender: gender,
        address: address
      };

      try {
        let res;
        if (id) {
          res = await fetch(`/api/students/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        } else {
          res = await fetch('/api/students', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        }
        const data = await res.json();
        if (data.success) {
          closeModal('student-modal');
          loadStudents();
        } else {
          alert('Error: ' + data.message);
        }
      } catch (err) {
        alert('Network error saving student');
      }
    });
  }

  // Bulk Upload Modal
  if (bulkBtn) {
    bulkBtn.addEventListener('click', () => {
      document.getElementById('bulk-file-input').value = '';
      document.getElementById('bulk-status-box').style.display = 'none';
      openModal('bulk-modal');
    });
  }

  const submitBulkBtn = document.getElementById('submit-bulk-upload-btn');
  if (submitBulkBtn) {
    submitBulkBtn.addEventListener('click', async () => {
      const fileInput = document.getElementById('bulk-file-input');
      if (!fileInput.files.length) {
        alert('Please select an Excel or CSV file first.');
        return;
      }

      const file = fileInput.files[0];
      const formData = new FormData();
      formData.append('file', file);

      const statusBox = document.getElementById('bulk-status-box');
      statusBox.style.display = 'block';
      statusBox.innerHTML = '<span style="color: var(--primary);">Uploading and importing students...</span>';

      try {
        const res = await fetch('/api/students/bulk-import', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (data.success) {
          statusBox.innerHTML = `<span style="color: var(--success); font-weight: 600;">${data.message}</span>`;
          setTimeout(() => {
            closeModal('bulk-modal');
            loadStudents();
          }, 1500);
        } else {
          statusBox.innerHTML = `<span style="color: var(--danger); font-weight: 600;">Import failed: ${data.message}</span>`;
        }
      } catch (err) {
        statusBox.innerHTML = '<span style="color: var(--danger);">Upload error.</span>';
      }
    });
  }

  // Automatic Batch Student Photos Upload
  const batchPhotosBtn = document.getElementById('batch-photos-btn');
  if (batchPhotosBtn) {
    batchPhotosBtn.addEventListener('click', () => {
      document.getElementById('batch-photos-input').value = '';
      document.getElementById('photos-status-box').style.display = 'none';
      openModal('photos-modal');
    });
  }

  const submitBatchPhotosBtn = document.getElementById('submit-batch-photos-btn');
  if (submitBatchPhotosBtn) {
    submitBatchPhotosBtn.addEventListener('click', async () => {
      const fileInput = document.getElementById('batch-photos-input');
      if (!fileInput.files.length) {
        alert('Please select photo files or a .ZIP archive.');
        return;
      }

      const formData = new FormData();
      for (let i = 0; i < fileInput.files.length; i++) {
        formData.append('files', fileInput.files[i]);
      }

      const statusBox = document.getElementById('photos-status-box');
      statusBox.style.display = 'block';
      statusBox.innerHTML = '<span style="color: var(--primary);">Matching and attaching photos...</span>';

      try {
        const res = await fetch('/api/students/bulk-photos', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (data.success) {
          statusBox.innerHTML = `
            <div style="color: var(--success); font-weight: 700; margin-bottom: 4px;">
              ✅ ${data.matched_count} photos linked to students!
            </div>
            ${data.unmatched_count > 0 ? `<div style="color: var(--warning); font-size: 11px;">⚠️ ${data.unmatched_count} photos could not be matched.</div>` : ''}
          `;
          setTimeout(() => {
            closeModal('photos-modal');
            loadStudents();
          }, 1800);
        } else {
          statusBox.innerHTML = `<span style="color: var(--danger);">${data.message}</span>`;
        }
      } catch (err) {
        statusBox.innerHTML = '<span style="color: var(--danger);">Upload error.</span>';
      }
    });
  }
}

async function loadStudents() {
  try {
    const res = await fetch('/api/students');
    const data = await res.json();
    allStudentsMasterList = data.students || [];
    studentsList = allStudentsMasterList;
    renderStudentsTable();
    populateLeaveStudentSelector(allStudentsMasterList);
  } catch (err) {
    console.error('Error loading students:', err);
  }
}

window.setAdminStudentQuickFilter = function(type) {
  const classEl = document.getElementById('student-class-filter');
  const genderEl = document.getElementById('student-gender-filter');
  const photoEl = document.getElementById('student-photo-filter');
  const searchEl = document.getElementById('student-search-input');
  if (searchEl) searchEl.value = '';

  // Visual active highlight
  document.querySelectorAll('.admin-quick-filter-btn').forEach(btn => {
    btn.style.boxShadow = 'none';
    btn.style.fontWeight = '500';
  });
  const currentBtn = document.getElementById(`quick-filter-${type}`);
  if (currentBtn) {
    currentBtn.style.boxShadow = '0 0 0 2px var(--primary)';
    currentBtn.style.fontWeight = '700';
  }

  if (type === 'all') {
    window.currentMissingDetailsFilter = null;
    if (classEl) classEl.value = '';
    if (genderEl) genderEl.value = '';
    if (photoEl) photoEl.value = '';
  } else if (type === 'boys-missing') {
    window.currentMissingDetailsFilter = null;
    if (classEl) classEl.value = '';
    if (genderEl) genderEl.value = 'Male';
    if (photoEl) photoEl.value = 'missing';
  } else if (type === 'boys-done') {
    window.currentMissingDetailsFilter = null;
    if (classEl) classEl.value = '';
    if (genderEl) genderEl.value = 'Male';
    if (photoEl) photoEl.value = 'has';
  } else if (type === 'girls') {
    window.currentMissingDetailsFilter = null;
    if (classEl) classEl.value = '';
    if (genderEl) genderEl.value = 'Female';
    if (photoEl) photoEl.value = '';
  } else if (type === 'missing-father') {
    window.currentMissingDetailsFilter = 'father';
    if (classEl) classEl.value = '';
    if (genderEl) genderEl.value = '';
    if (photoEl) photoEl.value = '';
  }

  if (!allStudentsMasterList || !allStudentsMasterList.length) {
    loadStudents();
  } else {
    renderStudentsTable();
  }
};

function renderStudentsTable() {
  const tbody = document.getElementById('students-table-body');
  if (!tbody) return;

  const classVal = document.getElementById('student-class-filter')?.value || '';
  const genderVal = document.getElementById('student-gender-filter')?.value || '';
  const photoVal = document.getElementById('student-photo-filter')?.value || '';
  const searchVal = (document.getElementById('student-search-input')?.value || '').toLowerCase().trim();

  const source = (allStudentsMasterList && allStudentsMasterList.length) ? allStudentsMasterList : studentsList;

  const filtered = source.filter(s => {
    // 1. Class filter
    if (classVal && s.class_name !== classVal) return false;

    // 2. Search filter
    if (searchVal) {
      const match = (s.full_name || '').toLowerCase().includes(searchVal) ||
             (s.student_code || '').toLowerCase().includes(searchVal) ||
             (s.roll_no || '').toLowerCase().includes(searchVal) ||
             (s.father_name || '').toLowerCase().includes(searchVal);
      if (!match) return false;
    }

    // 3. Gender filter
    if (genderVal) {
      const sGender = (s.gender || 'Male').toLowerCase();
      if (sGender !== genderVal.toLowerCase()) return false;
    }

    // 4. Photo filter
    const hasPhoto = Boolean(s.photo_url && s.photo_url.trim());
    if (photoVal === 'missing' && hasPhoto) return false;
    if (photoVal === 'has' && !hasPhoto) return false;

    // 5. Missing Details filter
    if (window.currentMissingDetailsFilter === 'father') {
      const fn = (s.father_name || '').trim();
      if (fn && fn !== '-' && fn !== 'N/A' && fn !== 'Unknown') return false;
    }

    return true;
  });

  const countBadge = document.getElementById('student-count-badge');
  if (countBadge) {
    countBadge.textContent = `Showing ${filtered.length} of ${source.length} Students`;
  }

  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 28px; color: var(--text-muted); font-size: 13px;">🔍 No students match the selected filters.</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(s => {
    const isGirl = (s.gender || '').toLowerCase() === 'female';
    const hasPhoto = Boolean(s.photo_url && s.photo_url.trim());

    let photoThumb = '';
    if (hasPhoto) {
      photoThumb = `<img src="${s.photo_url}" style="width: 26px; height: 32px; border-radius: 4px; object-fit: cover; border: 1px solid var(--border);">`;
    } else if (isGirl) {
      photoThumb = `<div title="Photo exempt (Female)" style="width: 26px; height: 32px; border-radius: 4px; background: #fdf2f8; border: 1px dashed #f472b6; display: flex; align-items: center; justify-content: center; font-size: 13px;">👧</div>`;
    } else {
      photoThumb = `<div title="Needs Photo (Boy)" style="width: 26px; height: 32px; border-radius: 4px; background: #fef2f2; border: 1.5px dashed #ef4444; display: flex; align-items: center; justify-content: center; font-size: 12px; color: #ef4444;">⚪</div>`;
    }

    const genderBadge = isGirl
      ? `<span style="font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 4px; background: #fce7f3; color: #db2777; border: 1px solid #fbcfe8;">👧 Girl</span>`
      : `<span style="font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 4px; background: #e0f2fe; color: #0284c7; border: 1px solid #bae6fd;">👦 Boy</span>`;

    return `
      <tr>
        <td><code>${s.student_code}</code></td>
        <td><strong>${s.roll_no}</strong></td>
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            ${photoThumb}
            <div>
              <div style="font-weight: 700;">${s.full_name}</div>
              ${!hasPhoto && !isGirl ? '<span style="font-size: 10px; color: #ef4444; font-weight: 700;">⚪ Needs Photo</span>' : ''}
              ${!hasPhoto && isGirl ? '<span style="font-size: 10px; color: #db2777; font-weight: 600;">👧 Exempt</span>' : ''}
            </div>
          </div>
        </td>
        <td>
          ${(s.father_name && s.father_name.trim() && s.father_name.trim() !== '-') 
            ? s.father_name 
            : '<span style="color: #b91c1c; font-weight: 700; background: #fee2e2; padding: 2px 7px; border-radius: 4px; font-size: 10.5px; border: 1px solid #fecaca;" title="Missing Father Name">⚠️ Missing Father</span>'}
        </td>
        <td><span style="color: var(--primary); font-weight: 600;">${s.class_name}</span></td>
        <td>${s.parent_phone || '-'}</td>
        <td>${genderBadge}</td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="viewQrCode('${s.student_code}', '${escapeHtml(s.full_name)}')">
            📷 QR
          </button>
        </td>
        <td>
          <div style="display: flex; gap: 4px;">
            <button class="btn btn-secondary btn-sm" onclick="editStudent(${s.id})">✏️ Edit</button>
            <a href="/print/cards?student_id=${s.id}" target="_blank" class="btn btn-secondary btn-sm" title="Print Card">🖨️ Card</a>
            <button class="btn btn-danger btn-sm" onclick="deleteStudent(${s.id}, '${escapeHtml(s.full_name)}')">🗑️</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

window.viewQrCode = async function(studentCode, name) {
  try {
    const res = await fetch(`/api/students/qr/${studentCode}`);
    const data = await res.json();
    if (data.qr_image) {
      document.getElementById('qr-view-title').textContent = `${name}'s QR Code`;
      document.getElementById('qr-view-img').src = data.qr_image;
      document.getElementById('qr-view-code').textContent = studentCode;
      openModal('qr-view-modal');
    }
  } catch (e) {
    alert('Failed to load QR code');
  }
};

window.editStudent = function(id) {
  const s = studentsList.find(item => item.id === id);
  if (!s) return;

  document.getElementById('stu-id').value = s.id;
  document.getElementById('student-modal-title').textContent = 'Edit Student Details';
  document.getElementById('stu-name').value = s.full_name;
  document.getElementById('stu-father').value = s.father_name || '';
  document.getElementById('stu-class').value = s.class_name;
  document.getElementById('stu-roll').value = s.roll_no;
  document.getElementById('stu-phone').value = s.parent_phone || '';
  document.getElementById('stu-gender').value = s.gender || 'Male';
  document.getElementById('stu-address').value = s.address || 'Loi Shalman';

  openModal('student-modal');
};

window.deleteStudent = async function(id, name) {
  if (!confirm(`Are you sure you want to remove student "${name}"?`)) return;

  try {
    const res = await fetch(`/api/students/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      loadStudents();
    } else {
      alert('Delete failed: ' + data.message);
    }
  } catch (err) {
    alert('Error deleting student');
  }
};


// --- TAB 3: PRINT CARDS & STICKERS ---
function initCards() {
  const printCardsBtn = document.getElementById('launch-print-cards-btn');
  const printStickersBtn = document.getElementById('launch-print-stickers-btn');
  const classSelect = document.getElementById('print-class-select');

  if (printCardsBtn) {
    printCardsBtn.addEventListener('click', () => {
      const cls = classSelect.value;
      window.open(`/print/cards?class_name=${cls}`, '_blank');
    });
  }

  if (printStickersBtn) {
    printStickersBtn.addEventListener('click', () => {
      const cls = classSelect.value;
      window.open(`/print/stickers?class_name=${cls}`, '_blank');
    });
  }
}


// --- TAB 4: REPORTS & ANALYTICS ---
function initReports() {
  const loadBtn = document.getElementById('rep-load-btn');
  const excelBtn = document.getElementById('rep-excel-btn');

  if (loadBtn) loadBtn.addEventListener('click', loadReportsData);
  if (excelBtn) {
    excelBtn.addEventListener('click', () => {
      const start = document.getElementById('rep-start-date').value;
      const end = document.getElementById('rep-end-date').value;
      const cls = document.getElementById('rep-class-select').value;
      window.location.href = `/api/reports/export-excel?start_date=${start}&end_date=${end}&class_name=${cls}`;
    });
  }
}

async function loadReportsData() {
  const start = document.getElementById('rep-start-date').value;
  const end = document.getElementById('rep-end-date').value;
  const cls = document.getElementById('rep-class-select').value;

  try {
    const res = await fetch(`/api/reports/period-summary?start_date=${start}&end_date=${end}&class_name=${cls}`);
    const data = await res.json();

    document.getElementById('rep-stat-total').textContent = data.total_students || 0;
    document.getElementById('rep-stat-present').textContent = data.present_marks || 0;
    document.getElementById('rep-stat-late').textContent = data.late_marks || 0;
    document.getElementById('rep-stat-absent').textContent = data.absent_marks || 0;

    // Load consecutive absentees alert
    loadConsecutiveAbsentees();
  } catch (err) {
    console.error('Error loading report data:', err);
  }
}

async function loadConsecutiveAbsentees() {
  const listEl = document.getElementById('consecutive-absent-list');
  if (!listEl) return;

  try {
    const res = await fetch('/api/reports/consecutive-absentees?days=3');
    const data = await res.json();
    const students = data.consecutive_absentees || [];

    if (!students.length) {
      listEl.innerHTML = '<span style="color: #047857; font-weight: 600;">✅ Excellent! No students have been absent for 3 or more consecutive days.</span>';
      return;
    }

    listEl.innerHTML = `
      <div style="margin-bottom: 8px;">The following ${students.length} students have missed 3+ consecutive days of school:</div>
      <ul style="padding-left: 20px;">
        ${students.map(s => `
          <li style="margin-bottom: 4px;">
            <strong>${s.full_name}</strong> (Class: ${s.class_name}, Roll: ${s.roll_no}) — 
            Absent for <strong>${s.consecutive_days} days</strong> | 
            Parent Phone: <a href="tel:${s.parent_phone}">${s.parent_phone || 'No phone'}</a>
          </li>
        `).join('')}
      </ul>
    `;
  } catch (err) {
    listEl.textContent = 'Could not calculate consecutive absentees.';
  }
}


// --- TAB 5: LEAVE MANAGEMENT ---
function initLeaves() {
  const addBtn = document.getElementById('add-leave-btn');
  const saveBtn = document.getElementById('save-leave-btn');

  if (addBtn) addBtn.addEventListener('click', () => openModal('leave-modal'));

  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      const stuId = document.getElementById('leave-student-select').value;
      const start = document.getElementById('leave-start-date').value;
      const end = document.getElementById('leave-end-date').value;
      const type = document.getElementById('leave-type-select').value;
      const reason = document.getElementById('leave-reason').value;

      if (!stuId) {
        alert('Please select a student.');
        return;
      }

      try {
        const res = await fetch('/api/leaves', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            student_id: parseInt(stuId),
            start_date: start,
            end_date: end,
            leave_type: type,
            reason: reason
          })
        });
        const data = await res.json();
        if (data.success) {
          closeModal('leave-modal');
          loadLeaves();
        } else {
          alert('Error registering leave: ' + data.message);
        }
      } catch (err) {
        alert('Error saving leave');
      }
    });
  }
}

function populateLeaveStudentSelector(students) {
  const sel = document.getElementById('leave-student-select');
  if (!sel) return;
  sel.innerHTML = '<option value="">-- Choose student --</option>' + 
    students.map(s => `<option value="${s.id}">${s.full_name} (${s.class_name} - Roll ${s.roll_no})</option>`).join('');
}

async function loadLeaves() {
  const tbody = document.getElementById('leaves-table-body');
  if (!tbody) return;

  try {
    const res = await fetch('/api/leaves');
    const data = await res.json();
    const leaves = data.leaves || [];

    if (!leaves.length) {
      tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 24px; color: var(--text-muted);">No student leave records registered.</td></tr>';
      return;
    }

    tbody.innerHTML = leaves.map(l => `
      <tr>
        <td><code>${l.student_code}</code></td>
        <td><strong>${l.full_name}</strong></td>
        <td>${l.class_name}</td>
        <td>${l.roll_no}</td>
        <td>${l.start_date}</td>
        <td>${l.end_date}</td>
        <td><span class="badge badge-leave">${l.leave_type}</span></td>
        <td>${l.reason || '-'}</td>
        <td>
          <button class="btn btn-danger btn-sm" onclick="cancelLeave(${l.id})">Cancel</button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Error loading leaves:', err);
  }
}

window.cancelLeave = async function(id) {
  if (!confirm('Are you sure you want to cancel this leave?')) return;
  try {
    const res = await fetch(`/api/leaves/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) loadLeaves();
  } catch (err) {
    alert('Error cancelling leave');
  }
};


// --- TAB 6: SETTINGS & N8N ---
function initSettings() {
  const saveSettingsBtn = document.getElementById('save-settings-btn');
  const saveN8nBtn = document.getElementById('save-n8n-btn');
  const testN8nBtn = document.getElementById('test-n8n-btn');
  const updatePwdBtn = document.getElementById('update-pwd-btn');

  if (saveSettingsBtn) {
    saveSettingsBtn.addEventListener('click', async () => {
      const schoolName = document.getElementById('set-school-name').value.trim();
      const schoolAddress = document.getElementById('set-school-address').value.trim();
      const startTime = document.getElementById('set-start-time').value;
      const lateTime = document.getElementById('set-late-time').value;
      const endTime = document.getElementById('set-end-time').value;
      const classesRaw = document.getElementById('set-classes-list').value;

      const classesArray = classesRaw.split(',').map(s => s.trim()).filter(Boolean);

      try {
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            school_name: schoolName,
            school_address: schoolAddress,
            school_start_time: startTime,
            late_threshold_time: lateTime,
            school_end_time: endTime,
            classes: JSON.stringify(classesArray)
          })
        });
        const data = await res.json();
        if (data.success) {
          alert('Settings saved successfully!');
          window.location.reload();
        }
      } catch (err) {
        alert('Error saving settings');
      }
    });
  }

  if (saveN8nBtn) {
    saveN8nBtn.addEventListener('click', async () => {
      const enabled = document.getElementById('set-n8n-enabled').checked ? '1' : '0';
      const url = document.getElementById('set-n8n-url').value.trim();
      const secret = document.getElementById('set-n8n-secret').value.trim();

      try {
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            n8n_notifications_enabled: enabled,
            n8n_webhook_url: url,
            n8n_webhook_secret: secret
          })
        });
        const data = await res.json();
        if (data.success) {
          alert('n8n WhatsApp settings saved!');
        }
      } catch (err) {
        alert('Error saving n8n configuration');
      }
    });
  }

  if (testN8nBtn) {
    testN8nBtn.addEventListener('click', async () => {
      const url = document.getElementById('set-n8n-url').value.trim();
      const secret = document.getElementById('set-n8n-secret').value.trim();
      const resSpan = document.getElementById('n8n-test-result');

      if (!url) {
        alert('Please enter your n8n Webhook URL first.');
        return;
      }

      resSpan.textContent = 'Pinging n8n...';
      resSpan.style.color = 'var(--primary)';

      try {
        const res = await fetch('/api/settings/test-n8n', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: url, secret: secret })
        });
        const data = await res.json();
        if (data.success) {
          resSpan.textContent = `✅ Connected! HTTP ${data.status_code}`;
          resSpan.style.color = 'var(--success)';
        } else {
          resSpan.textContent = `❌ Ping failed: ${data.error || 'HTTP ' + data.status_code}`;
          resSpan.style.color = 'var(--danger)';
        }
      } catch (err) {
        resSpan.textContent = '❌ Failed to reach server.';
        resSpan.style.color = 'var(--danger)';
      }
    });
  }

  if (updatePwdBtn) {
    updatePwdBtn.addEventListener('click', async () => {
      const curr = document.getElementById('pwd-current').value;
      const nw = document.getElementById('pwd-new').value;

      if (!curr || !nw) {
        alert('Please fill in both current and new passwords.');
        return;
      }

      try {
        const res = await fetch('/api/auth/change-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ current_password: curr, new_password: nw })
        });
        const data = await res.json();
        if (data.success) {
          alert('Password updated successfully! Please login with your new password.');
          window.location.href = '/login';
        } else {
          alert('Failed: ' + data.message);
        }
      } catch (err) {
        alert('Network error updating password');
      }
    });
  }
}

// --- AUTH & LOGOUT ---
function initAuth() {
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST' });
      window.location.href = '/login';
    });
  }
}

// Security HTML escaper
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
