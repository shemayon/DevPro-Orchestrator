import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Search, Code2, TestTube2, FileText,
  Plus, Play, RefreshCcw, CheckCircle2,
  AlertCircle, Clock, Loader2, Activity,
  Zap, BarChart3, X, ChevronDown, Trash2
} from 'lucide-react';

const API = '/api';

const AGENT_META = {
  research_expert:       { Icon: Search,    label: 'Research',      color: '#818cf8' },
  coding_expert:         { Icon: Code2,     label: 'Coding',        color: '#34d399' },
  testing_expert:        { Icon: TestTube2, label: 'Testing',       color: '#f472b6' },
  documentation_expert:  { Icon: FileText,  label: 'Documentation', color: '#fbbf24' },
};

const STATUS_CONFIG = {
  not_started:  { label: 'Not Started', cls: 's-not_started', Icon: Clock },
  in_progress:  { label: 'In Progress', cls: 's-in_progress', Icon: Activity },
  completed:    { label: 'Completed',   cls: 's-completed',   Icon: CheckCircle2 },
  blocked:      { label: 'Blocked',     cls: 's-blocked',     Icon: AlertCircle },
  failed:       { label: 'Failed',      cls: 's-failed',      Icon: AlertCircle },
};

// ── Toast ──────────────────────────────────────
function Toast({ msg, type, onClose }) {
  useEffect(() => { const t = setTimeout(onClose, 3500); return () => clearTimeout(t); }, []);
  return (
    <div className={`toast toast-${type}`}>
      {type === 'error' ? <AlertCircle size={15}/> : <CheckCircle2 size={15}/>}
      {msg}
      <button className="btn-text" style={{padding:'0 0 0 .4rem'}} onClick={onClose}><X size={13}/></button>
    </div>
  );
}

// ── Agent Card ─────────────────────────────────
function AgentCard({ name, info, delay }) {
  const meta = AGENT_META[name] || { Icon: Zap, label: name, color: '#6366f1' };
  const { Icon, label, color } = meta;
  return (
    <div className="agent-card glass" style={{'--delay': delay + 'ms', animationDelay: delay + 'ms'}}>
      <div className="agent-icon-wrap" style={{borderColor: color + '44', background: color + '18'}}>
        <Icon size={20} color={color}/>
      </div>
      <div className="agent-name">{label}</div>
      <div className="badge badge-active" style={{marginBottom:'.5rem'}}>
        <span className="badge-dot"/>ACTIVE
      </div>
      <div className="agent-tools">
        {(info.tools || []).map(t => <code key={t} className="tool-chip">{t}</code>)}
      </div>
    </div>
  );
}

// ── Task Row ───────────────────────────────────
function TaskRow({ task, onExecute, onDelete, executing }) {
  const s = STATUS_CONFIG[task.status] || STATUS_CONFIG.not_started;
  const canRun = task.status === 'not_started' || task.status === 'failed' || task.status === 'blocked';
  const isRunning = executing === task.id;
  return (
    <tr>
      <td><span style={{color:'var(--text-muted)',fontFamily:'monospace',fontSize:'.78rem'}}>#{task.id}</span></td>
      <td>
        <div className="task-title">{task.title}</div>
        {task.description && (
          <div className="task-desc">{task.description.slice(0, 70)}{task.description.length > 70 ? '…' : ''}</div>
        )}
      </td>
      <td><span className="component-chip">{task.component_area}</span></td>
      <td>
        <span className={`status-pill ${s.cls}`}>
          <s.Icon size={11}/>{s.label}
        </span>
      </td>
      <td>
        {task.status === 'completed'
          ? <CheckCircle2 size={16} color="var(--green)" style={{display:'block'}}/>
          : canRun
            ? (
              <button className="btn btn-primary btn-sm" onClick={() => onExecute(task.id)} disabled={executing !== null}>
                {isRunning ? <Loader2 size={13} className="spin"/> : <Play size={13}/>}
                {isRunning ? 'Running…' : 'Execute'}
              </button>
            )
            : <span style={{color:'var(--text-muted)',fontSize:'.78rem'}}>—</span>
        }
      </td>
      <td>
        <button
          className="icon-btn"
          title="Delete task"
          style={{color:'var(--red,#f87171)'}}
          onClick={() => { if (window.confirm(`Delete task #${task.id}?`)) onDelete(task.id); }}
          disabled={executing !== null}
        >
          <Trash2 size={14}/>
        </button>
      </td>
    </tr>
  );
}

// ── New Task Modal ─────────────────────────────
function NewTaskModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ title:'', description:'', component_area:'Research', priority:'medium' });
  const [loading, setLoading] = useState(false);

  const set = (k, v) => setForm(f => ({...f, [k]: v}));

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post(`${API}/tasks`, form);
      onCreated('Task created successfully!');
      onClose();
    } catch {
      onCreated('Failed to create task.', true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal glass" onClick={e => e.stopPropagation()}>
        <h2>⚡ New Task</h2>

        <form onSubmit={submit}>
          <div className="form-group">
            <label>Task Title</label>
            <input required placeholder="e.g. Research LangGraph patterns" value={form.title} onChange={e => set('title', e.target.value)}/>
          </div>
          <div className="form-group">
            <label>Description</label>
            <textarea placeholder="What should the agents achieve?" value={form.description} onChange={e => set('description', e.target.value)}/>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Component</label>
              <select value={form.component_area} onChange={e => set('component_area', e.target.value)}>
                {['Research','Core','Integrations','UI','Testing','Documentation'].map(o => <option key={o}>{o}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Priority</label>
              <select value={form.priority} onChange={e => set('priority', e.target.value)}>
                <option value="high">🔴 High</option>
                <option value="medium">🟡 Medium</option>
                <option value="low">🟢 Low</option>
              </select>
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn-text" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? <Loader2 size={14} className="spin"/> : <Zap size={14}/>}
              {loading ? 'Creating…' : 'Create Task'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── App ────────────────────────────────────────
export default function App() {
  const [status, setStatus]     = useState(null);
  const [tasks, setTasks]       = useState([]);
  const [booting, setBooting]   = useState(true);
  const [executing, setExecuting] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [toast, setToast]        = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const showToast = (msg, isError = false) =>
    setToast({ msg, type: isError ? 'error' : 'success' });

  const fetchAll = async (quiet = false) => {
    if (!quiet) setRefreshing(true);
    try {
      const [s, t] = await Promise.all([
        axios.get(`${API}/status`),
        axios.get(`${API}/tasks`),
      ]);
      setStatus(s.data);
      setTasks(t.data);
    } catch {
      if (!quiet) showToast('Cannot reach backend', true);
    } finally {
      setBooting(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const id = setInterval(() => fetchAll(true), 5000);
    return () => clearInterval(id);
  }, []);

  const executeTask = async (id) => {
    setExecuting(id);
    try {
      await axios.post(`${API}/tasks/${id}/execute`);
      showToast(`Task #${id} completed ✓`);
      fetchAll(true);
    } catch {
      showToast(`Task #${id} failed`, true);
    } finally {
      setExecuting(null);
    }
  };

  const deleteTask = async (id) => {
    try {
      await axios.delete(`${API}/tasks/${id}`);
      setTasks(prev => prev.filter(t => t.id !== id));
      showToast(`Task #${id} deleted`);
    } catch {
      showToast(`Could not delete task #${id}`, true);
    }
  };

  const stats = status?.task_statistics || {};
  const agents = status?.agents || {};

  if (booting) return (
    <div className="loading-screen">
      <div className="loading-ring"/>
      <p>Initializing Agent Network…</p>
    </div>
  );

  return (
    <div className="dashboard">
      {/* ── Header ── */}
      <header className="header">
        <div>
          <div className="header-badge"><span className="dot"/>{status?.system_status?.toUpperCase() || 'ACTIVE'}</div>
          <h1>DevPro Orchestrator</h1>
          <p className="header-sub">Autonomous Multi-Agent Orchestration System</p>
        </div>
        <div className="header-actions">
          <div className="stats-pills">
            <div className="stats-pill"><span>{stats.total_tasks ?? 0}</span> Tasks</div>
            <div className="stats-pill"><span>{Math.round(stats.completion_percentage ?? 0)}%</span> Done</div>
            <div className="stats-pill"><span>{(stats.remaining_hours ?? 0).toFixed(1)}h</span> Left</div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={15}/> New Task
          </button>
        </div>
      </header>

      {/* ── Agent Network ── */}
      <section>
        <p className="section-label">Agent Network</p>
        <div className="agents-grid">
          {Object.entries(agents).map(([name, info], i) => (
            <AgentCard key={name} name={name} info={info} delay={i * 80}/>
          ))}
        </div>
      </section>

      {/* ── Stats Bar ── */}
      <div className="glass stats-bar">
        {[
          { label:'Total Tasks', value: stats.total_tasks ?? 0 },
          { label:'Success Rate', value: `${Math.round(stats.completion_percentage ?? 0)}%` },
          { label:'Remaining Effort', value: `${(stats.remaining_hours ?? 0).toFixed(1)}h` },
        ].map(({ label, value }) => (
          <div key={label} className="stat-item">
            <div className="stat-label">{label}</div>
            <div className="stat-value">{value}</div>
          </div>
        ))}
      </div>

      {/* ── Task Table ── */}
      <div className="glass">
        <div className="section-header">
          <span className="section-title"><BarChart3 size={16} style={{display:'inline',marginRight:'.4rem'}}/>Lifecycle Management</span>
          <button className={`icon-btn ${refreshing ? 'spinning' : ''}`} onClick={() => fetchAll()}>
            <RefreshCcw size={14}/>
          </button>
        </div>
        <div className="task-table-wrap">
          {tasks.length === 0
            ? (
              <div className="empty-state">
                <Zap size={40}/>
                <p>No tasks yet. Hit <strong>+ New Task</strong> to get started.</p>
              </div>
            )
            : (
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Task</th>
                    <th>Component</th>
                    <th>Status</th>
                    <th>Action</th>
                    <th>Delete</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map(t => (
                    <TaskRow key={t.id} task={t} onExecute={executeTask} onDelete={deleteTask} executing={executing}/>
                  ))}
                </tbody>
              </table>
            )
          }
        </div>
      </div>

      {/* ── Modal ── */}
      {showModal && (
        <NewTaskModal
          onClose={() => setShowModal(false)}
          onCreated={(msg, isErr) => { showToast(msg, isErr); fetchAll(true); }}
        />
      )}

      {/* ── Toast ── */}
      {toast && <Toast {...toast} onClose={() => setToast(null)}/>}
    </div>
  );
}
