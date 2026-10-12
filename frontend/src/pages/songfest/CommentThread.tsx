// frontend/src/pages/songfest/CommentThread.tsx
// 回報串的「閒聊」：每首投稿底下的留言
import { useEffect, useState, type FormEvent } from 'react';
import {
  apiErrorMessage, deleteSubmissionComment, fetchSubmissionComments, formatDateTime, postSubmissionComment,
  type SubmissionComment,
} from '../../api/songfest';

interface Props {
  submissionId: number;
  onCountChange: (count: number) => void;
}

export default function CommentThread({ submissionId, onCountChange }: Props) {
  const [comments, setComments] = useState<SubmissionComment[] | null>(null);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    fetchSubmissionComments(submissionId)
      .then(setComments)
      .catch(() => setError('留言載入失敗'));
  }, [submissionId]);

  const update = (next: SubmissionComment[]) => {
    setComments(next);
    onCountChange(next.length);
  };

  const send = async (e: FormEvent) => {
    e.preventDefault();
    if (!draft.trim() || comments === null) return;
    setSending(true);
    setError(null);
    try {
      const created = await postSubmissionComment(submissionId, draft.trim());
      update([...comments, created]);
      setDraft('');
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSending(false);
    }
  };

  const remove = async (id: number) => {
    if (comments === null) return;
    try {
      await deleteSubmissionComment(id);
      update(comments.filter(c => c.id !== id));
    } catch (err) {
      setError(apiErrorMessage(err, '刪除失敗'));
    }
  };

  return (
    <div className="sf-comments">
      {comments === null && !error && <p className="sf-muted">載入中…</p>}
      {comments?.length === 0 && <p className="sf-muted">還沒有人閒聊。</p>}
      {comments?.map(c => (
        <div key={c.id} className="sf-comment">
          <strong>{c.username}</strong>
          <span className="sf-comment-text">{c.content}</span>
          <small className="sf-muted">{formatDateTime(c.createdAt)}</small>
          {c.canDelete && (
            <button type="button" className="sf-link-button" onClick={() => remove(c.id)}>刪除</button>
          )}
        </div>
      ))}
      <form className="sf-comment-form" onSubmit={send}>
        <input
          value={draft}
          onChange={e => setDraft(e.target.value)}
          maxLength={500}
          placeholder="閒聊幹話，但請勿吵架或洗版"
          aria-label="留言"
        />
        <button type="submit" className="sf-button" disabled={sending || !draft.trim()}>送出</button>
      </form>
      {error && <p className="sf-error">{error}</p>}
    </div>
  );
}
