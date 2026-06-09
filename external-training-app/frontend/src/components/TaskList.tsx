import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { ListTodo, X, Clock, Loader2, CheckCircle2, XCircle, Trash2 } from 'lucide-react';
import { useTaskContext, type TaskSummary } from '../contexts/TaskContext';

function StatusIcon({ status }: { status: TaskSummary['status'] }) {
  switch (status) {
    case 'pending': return <Clock size={16} className="task-icon pending" />;
    case 'running': return <Loader2 size={16} className="task-icon running spinning" />;
    case 'completed': return <CheckCircle2 size={16} className="task-icon completed" />;
    case 'failed': return <XCircle size={16} className="task-icon failed" />;
    case 'cancelled': return <XCircle size={16} className="task-icon cancelled" />;
    default: return null;
  }
}

function StatusBadge({ status }: { status: TaskSummary['status'] }) {
  const labels: Record<string, string> = {
    pending: '等待中', running: '运行中', completed: '已完成', failed: '失败', cancelled: '已取消',
  };
  return <span className={`task-badge ${status}`}>{labels[status] || status}</span>;
}

function formatTime(isoString?: string): string {
  if (!isoString) return '';
  return new Date(isoString).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function TaskItem({ task, onClick, onRemove }: {
  task: TaskSummary;
  onClick: () => void;
  onRemove: (e: React.MouseEvent) => void;
}) {
  const isTerminal = task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled';

  return (
    <div className="task-item" onClick={onClick}>
      <StatusIcon status={task.status} />
      <div className="task-item-content">
        <p className="task-item-title">{task.title}</p>
        <p className="task-item-time">
          {task.status === 'running' && task.startedAt
            ? `开始于 ${formatTime(task.startedAt)}`
            : task.completedAt ? `完成于 ${formatTime(task.completedAt)}` : `创建于 ${formatTime(task.createdAt)}`
          }
        </p>
      </div>
      <StatusBadge status={task.status} />
      {isTerminal && (
        <button onClick={onRemove} className="task-remove-btn" title="移除任务">
          <Trash2 size={14} />
        </button>
      )}
    </div>
  );
}

export function TaskList() {
  const { activeTasks, tasks, removeTask } = useTaskContext();
  const [isOpen, setIsOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node) &&
          buttonRef.current && !buttonRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const allTasks = Array.from(tasks.values());
  const activeCount = activeTasks.length;

  const handleTaskClick = (taskId: string) => {
    setIsOpen(false);
    navigate(`/tasks/${taskId}`);
  };

  const handleRemove = (e: React.MouseEvent, taskId: string) => {
    e.stopPropagation();
    removeTask(taskId);
  };

  return (
    <div className="task-list-wrapper">
      <button ref={buttonRef} onClick={() => setIsOpen(!isOpen)} className="task-trigger-btn">
        <ListTodo size={18} />
        <span>任务列表</span>
        {activeCount > 0 && <span className="task-badge-count">{activeCount}</span>}
      </button>

      {isOpen && (
        <div ref={panelRef} className="task-panel">
          <div className="task-panel-header">
            <h3>任务列表</h3>
            <button onClick={() => setIsOpen(false)} className="task-panel-close"><X size={16} /></button>
          </div>
          <div className="task-panel-body">
            {allTasks.length === 0 ? (
              <p className="task-empty">暂无任务</p>
            ) : (
              <>
                {activeTasks.length > 0 && (
                  <div>
                    <p className="task-group-label">进行中</p>
                    {activeTasks.map(task => (
                      <TaskItem key={task.id} task={task} onClick={() => handleTaskClick(task.id)} onRemove={(e) => handleRemove(e, task.id)} />
                    ))}
                  </div>
                )}
                {allTasks.filter(t => t.status !== 'pending' && t.status !== 'running').length > 0 && (
                  <div>
                    {activeTasks.length > 0 && <div className="task-divider" />}
                    <p className="task-group-label">已结束</p>
                    {allTasks.filter(t => t.status !== 'pending' && t.status !== 'running').map(task => (
                      <TaskItem key={task.id} task={task} onClick={() => handleTaskClick(task.id)} onRemove={(e) => handleRemove(e, task.id)} />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
