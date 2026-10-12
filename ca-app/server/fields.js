// Single source of truth for the Corrective Action schema.
// Field order mirrors the True Corp CA Register (REGISTER sheet, 38 columns).
// Each field: key (db column), th/en labels, type, group, required, dropdown list name.

export const LISTS = {
  level: ['Program', 'Individual'],
  source: ['QA monitoring', 'Complaint', 'Audit', 'Calibration', 'Analytics/Trend', 'Management review'],
  product: ['Postpaid', 'Prepaid', 'TOL', 'TVS', 'Cross-product'],
  error_type: ['Compliance Critical', 'Business Critical', 'Customer Critical', 'Non-critical'],
  priority: ['Compliance-critical', 'High', 'Medium', 'Low'],
  rca_method: ['5 Whys', 'Fishbone', 'Pareto', '3-layer RCA', 'Combined'],
  adri: ['Approach (design)', 'Deployment (execution)', 'N/A (individual)'],
  cause_agent_non: ['Agent-related', 'Non-agent (systemic)'],
  lever: ['Process redesign', 'Training redesign', 'KB/Content fix', 'Policy change', 'Tool/System fix', 'Coaching', 'PIP', 'Progressive discipline'],
  status: ['Open', 'In-progress', 'Verifying', 'Closed', 'Reopened'],
  effective: ['Yes', 'No', 'Pending'],
  sustained: ['Yes - 3+ points', 'Not yet', 'No - reopened'],
};

// SLA (days) by Error type — reference matrix from the Excel LISTS tab.
export const SLA_DAYS = {
  'Compliance Critical': 5,
  'Business Critical': 7,
  'Customer Critical': 14,
  'Non-critical': 30,
};

export const GROUPS = [
  { key: 'identify', th: 'ระบุ', en: 'Identify' },
  { key: 'problem', th: 'ปัญหา', en: 'Problem' },
  { key: 'containment', th: 'Containment', en: 'Containment' },
  { key: 'rootcause', th: 'Root cause', en: 'Root cause' },
  { key: 'action', th: 'Action plan', en: 'Action plan' },
  { key: 'verify', th: 'Verify', en: 'Verify' },
  { key: 'close', th: 'Close', en: 'Close' },
  { key: 'statusg', th: 'สถานะ', en: 'Status' },
  { key: 'individual', th: 'รายบุคคล (เมื่อ Level = Individual)', en: 'Individual (when Level = Individual)' },
];

// t = text, ta = textarea, date, select
export const FIELDS = [
  { key: 'ca_id', th: 'CA ID', en: 'CA ID', type: 't', group: 'identify', required: true },
  { key: 'raise_date', th: 'วันที่ raise', en: 'Raise date', type: 'date', group: 'identify', required: true },
  { key: 'raised_by', th: 'ผู้ raise', en: 'Raised by', type: 't', group: 'identify' },
  { key: 'level', th: 'Level', en: 'Level', type: 'select', list: 'level', group: 'identify', required: true },
  { key: 'source', th: 'Source', en: 'Source', type: 'select', list: 'source', group: 'identify' },
  { key: 'product', th: 'Product', en: 'Product', type: 'select', list: 'product', group: 'identify', required: true },

  { key: 'nonconformity', th: 'คำอธิบาย nonconformity', en: 'Nonconformity description', type: 'ta', group: 'problem', required: true },
  { key: 'txn_ref', th: 'Txn/Eval ID หรือ Trend ref', en: 'Txn/Eval ID or Trend ref', type: 't', group: 'problem' },
  { key: 'error_type', th: 'Error type', en: 'Error type', type: 'select', list: 'error_type', group: 'problem', required: true },
  { key: 'priority', th: 'Priority', en: 'Priority', type: 'select', list: 'priority', group: 'problem', required: true },

  { key: 'containment_correction', th: 'correction ทันที', en: 'Immediate correction', type: 'ta', group: 'containment' },
  { key: 'containment_owner', th: 'เจ้าของ containment', en: 'Containment owner', type: 't', group: 'containment' },
  { key: 'contain_date', th: 'วันที่ contain', en: 'Contain date', type: 'date', group: 'containment' },

  { key: 'rca_method', th: 'วิธี RCA', en: 'RCA method', type: 'select', list: 'rca_method', group: 'rootcause' },
  { key: 'root_cause', th: 'Root cause (สรุป)', en: 'Root cause (summary)', type: 'ta', group: 'rootcause' },
  { key: 'adri', th: 'Approach/Deployment', en: 'Approach/Deployment', type: 'select', list: 'adri', group: 'rootcause' },
  { key: 'cause_agent_non', th: 'Agent / Non-agent', en: 'Agent / Non-agent', type: 'select', list: 'cause_agent_non', group: 'rootcause' },

  { key: 'corrective_action', th: 'Corrective action', en: 'Corrective action', type: 'ta', group: 'action', required: true },
  { key: 'lever', th: 'Lever', en: 'Lever', type: 'select', list: 'lever', group: 'action' },
  { key: 'action_owner', th: 'เจ้าของ (ระบุชื่อ)', en: 'Action owner (name)', type: 't', group: 'action' },
  { key: 'due_date', th: 'Due date', en: 'Due date', type: 'date', group: 'action' },
  { key: 'preventive', th: 'Preventive (เกิดที่อื่น?)', en: 'Preventive (elsewhere?)', type: 'ta', group: 'action' },

  { key: 'target_metric', th: 'Metric เป้าหมาย', en: 'Target metric', type: 't', group: 'verify' },
  { key: 'baseline', th: 'Baseline', en: 'Baseline', type: 't', group: 'verify' },
  { key: 'result_after', th: 'ผล หลังแก้', en: 'Result after fix', type: 't', group: 'verify' },
  { key: 'effective', th: 'Effective?', en: 'Effective?', type: 'select', list: 'effective', group: 'verify' },
  { key: 'verified_by', th: 'ผู้ verify', en: 'Verified by', type: 't', group: 'verify' },

  { key: 'sustained', th: 'Sustained?', en: 'Sustained?', type: 'select', list: 'sustained', group: 'close' },
  { key: 'lessons_learned', th: 'Lessons learned', en: 'Lessons learned', type: 'ta', group: 'close' },

  { key: 'status', th: 'Status', en: 'Status', type: 'select', list: 'status', group: 'statusg', required: true },
  { key: 'sent_to_owner', th: 'Sent CA to Owner', en: 'Sent CA to Owner', type: 'date', group: 'statusg' },

  { key: 'agent', th: 'Agent', en: 'Agent', type: 't', group: 'individual' },
  { key: 'sup', th: 'Sup', en: 'Sup', type: 't', group: 'individual' },
  { key: 'n4', th: 'N-4', en: 'N-4', type: 't', group: 'individual' },
  { key: 'seb_section', th: 'seb section', en: 'Section', type: 't', group: 'individual' },
];

export const FIELD_KEYS = FIELDS.map((f) => f.key);
