import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ChevronUp,
  ChevronDown,
  ThumbsUp,
  MessageCircle,
  Eye,
  Grid3x3,
  ChevronRight,
  ChevronLeft,
  Volume2,
  VolumeX,
  SkipBack,
  SkipForward,
  Play,
  Pause,
  Send
} from 'lucide-react';
import { isAxiosError } from 'axios';
import { api, getAccessToken } from '../api/client';
import { categoryName } from '../api/club';
import Sidebar from '../components/Sidebar';
import { useAuth } from '../contexts/auth';
import '../styles/Works.css';

// 沒有縮圖、或圖片載入失敗時用的佔位圖（frontend/public/images/placeholders/）
const PLACEHOLDER = {
  image: '/images/placeholders/work-image.svg',
  video: '/images/placeholders/work-video.svg',
  empty: '/images/placeholders/empty-works.svg',
};

/** 圖片載入失敗時換成佔位圖（只換一次，避免佔位圖也壞掉時無限迴圈） */
function makeFallback(kind: 'image' | 'video') {
  return (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    if (!img.dataset.fallback) {
      img.dataset.fallback = '1';
      img.src = PLACEHOLDER[kind];
    }
  };
}

// 類型定義（對應後端 NCUACG/club/views.py 的輸出）
interface Course {
  id: string;        // 後端的 slug，例如 114-upper
  name: string;
  color: 'blue' | 'green';
  category: string;
  workCount: number; // 已上架作品數
}

interface Work {
  id: number;
  course: string;
  title: string;
  author: string;
  type: 'video' | 'image';
  url: string;
  thumbnail: string | null;
  embedUrl: string | null; // YouTube 連結：用內嵌播放器，不能用 <video>
  lesson: { id: number; number: number | null; title: string } | null; // 來自哪一堂社課
  likes: number;
  views: number;
  commentCount: number; // 留言本體在開啟留言欄時另外抓
  isLiked: boolean;
  createdAt: string;
}

interface Comment {
  id: number;
  username: string;
  content: string;
  likes: number;
  isLiked: boolean;
  canDelete: boolean; // 本人或幹部才會是 true
  createdAt: string;
}

interface SortOption {
  type: 'time' | 'popularity';
  direction: 'asc' | 'desc';
}

type LikeResult = { likes: number; isLiked: boolean };

const Works: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();
  // 社課負責人與幹部可以在網站上架作品（管理成果牆）
  const canManage = Boolean(user?.courseLead) || user?.role === 'admin' || user?.role === 'superadmin';
  // 從社課介紹頁帶過來的種類，例如 /club/works?category=seiyuu；沒帶就顯示全部
  const [searchParams] = useSearchParams();
  const category = searchParams.get('category') || '';

  // 狀態管理
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<string>('');
  const [works, setWorks] = useState<Work[]>([]);
  // 只存 id，作品內容一律從 works 取，按讚/留言更新 works 時畫面才會同步
  const [selectedWorkId, setSelectedWorkId] = useState<number | null>(null);
  // 目前作品的留言（開啟留言欄時才抓）
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sortOption, setSortOption] = useState<SortOption>({ type: 'time', direction: 'desc' });
  const [showComments, setShowComments] = useState<boolean>(false);
  const [newComment, setNewComment] = useState<string>('');
  const [isGridView, setIsGridView] = useState<boolean>(false);

  // 播放器相關狀態
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [volume, setVolume] = useState<number>(100);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [showVolumeSlider, setShowVolumeSlider] = useState<boolean>(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const courseListRef = useRef<HTMLDivElement>(null);
  // 分類多到列表捲得動時才顯示上下捲動按鈕
  const [canScroll, setCanScroll] = useState(false);
  useEffect(() => {
    const el = courseListRef.current;
    setCanScroll(Boolean(el && el.scrollHeight > el.clientHeight + 1));
  }, [courses]);
  // 避免 StrictMode 下 effect 跑兩次而重複累加瀏覽數
  const lastViewedRef = useRef<number | null>(null);

  const imageFallback = makeFallback('image');
  const videoFallback = makeFallback('video');

  const selectedIndex = works.findIndex(w => w.id === selectedWorkId);
  const selectedWork = selectedIndex >= 0 ? works[selectedIndex] : null;

  // 分頁：一頁一件作品，下方頁碼就是「這個社課的第幾件作品」
  const totalPages = Math.max(works.length, 1);
  const currentPage = selectedIndex >= 0 ? selectedIndex + 1 : 1;
  const setCurrentPage = (page: number) => {
    const target = works[page - 1];
    if (target) setSelectedWorkId(target.id);
  };

  // 沒有社課可選時，作品 effect 不會跑，要自己把上一個種類的作品清掉
  const clearWorks = (error: string | null) => {
    setWorks([]);
    setSelectedWorkId(null);
    setLoadError(error);
    setLoading(false);
  };

  // 社課列表
  useEffect(() => {
    let cancelled = false;
    api.get<Course[]>('/club/courses/', { params: category ? { category } : undefined })
      .then(res => {
        if (cancelled) return;
        setCourses(res.data);
        // 預設選第一個有作品的社課（跳過「關於聲優社課」這類空分類），都沒有才選第一個
        const fallback = (res.data.find(c => c.workCount > 0) ?? res.data[0])?.id ?? '';
        setSelectedCourse(prev => (res.data.some(c => c.id === prev) ? prev : fallback));
        if (res.data.length === 0) clearWorks(null);
      })
      .catch(() => {
        if (cancelled) return;
        setCourses([]);
        setSelectedCourse('');
        clearWorks('社課列表載入失敗，請稍後再試');
      });
    return () => { cancelled = true; };
  }, [category]);

  // 作品列表：切換社課或排序時重抓（排序交給後端）
  useEffect(() => {
    if (!selectedCourse) return;
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    api.get<Work[]>('/club/works/', {
      params: { course: selectedCourse, sort: sortOption.type, order: sortOption.direction },
    })
      .then(res => {
        if (cancelled) return;
        setWorks(res.data);
        // 同一個社課換排序：留在原本那件作品；換社課：從第一件開始
        setSelectedWorkId(prev => (res.data.some(w => w.id === prev) ? prev : res.data[0]?.id ?? null));
      })
      .catch(() => {
        if (cancelled) return;
        setWorks([]);
        setSelectedWorkId(null);
        setLoadError('作品載入失敗，請稍後再試');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [selectedCourse, sortOption.type, sortOption.direction]);

  // 登出（含攔截器續命失敗的強制登出）後，畫面上的「已按讚」要跟著收掉
  useEffect(() => {
    if (isAuthenticated || getAccessToken()) return;
    setWorks(prev => (prev.some(w => w.isLiked) ? prev.map(w => ({ ...w, isLiked: false })) : prev));
    setComments(prev => (prev.some(c => c.isLiked) ? prev.map(c => ({ ...c, isLiked: false })) : prev));
  }, [isAuthenticated]);

  // 開啟留言欄或換作品時抓留言
  useEffect(() => {
    if (!showComments || selectedWorkId == null) return;
    let cancelled = false;
    const id = selectedWorkId;
    setComments([]);
    api.get<Comment[]>(`/club/works/${id}/comments/`)
      .then(res => { if (!cancelled) setComments(res.data); })
      .catch(() => { /* 留言載入失敗時留言欄保持空白 */ });
    return () => { cancelled = true; };
  }, [showComments, selectedWorkId]);

  // 換作品時：播放狀態歸零，並把瀏覽數 +1
  useEffect(() => {
    setIsPlaying(false);
    if (selectedWorkId == null || lastViewedRef.current === selectedWorkId) return;
    lastViewedRef.current = selectedWorkId;
    const id = selectedWorkId;
    api.post<{ views: number }>(`/club/works/${id}/view/`)
      .then(res => setWorks(prev => prev.map(w => (w.id === id ? { ...w, views: res.data.views } : w))))
      .catch(() => { /* 瀏覽數沒加到不影響觀看 */ });
  }, [selectedWorkId]);

  // 滾動處理
  const handleScroll = (direction: 'up' | 'down') => {
    if (courseListRef.current) {
      courseListRef.current.scrollTop += direction === 'down' ? 100 : -100;
    }
  };

  // 排序切換
  const toggleSort = () => {
    if (sortOption.type === 'time') {
      setSortOption({ type: 'popularity', direction: 'desc' });
    } else {
      setSortOption({ type: 'time', direction: sortOption.direction === 'desc' ? 'asc' : 'desc' });
    }
  };

  // 排序方向切換
  const toggleSortDirection = () => {
    setSortOption(prev => ({
      ...prev,
      direction: prev.direction === 'desc' ? 'asc' : 'desc'
    }));
  };

  // 播放器控制：isPlaying 由 <video> 的 play/pause/ended 事件同步，這裡只下指令
  const togglePlay = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      // 檔案 404、格式不支援時 play() 會 reject；狀態維持「暫停」即可
      video.play().catch(() => setIsPlaying(false));
    } else {
      video.pause();
    }
  }, []);

  const skipTime = useCallback((seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime += seconds;
    }
  }, []);

  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const handleVolumeChange = (value: number) => {
    setVolume(value);
    if (videoRef.current) {
      videoRef.current.volume = value / 100;
    }
  };

  // 互動功能
  const patchWork = (id: number, patch: Partial<Work>) =>
    setWorks(prev => prev.map(w => (w.id === id ? { ...w, ...patch } : w)));

  const askLogin = (action: string) => {
    if (window.confirm(`登入後才能${action}，要前往登入頁嗎？`)) navigate('/login');
  };

  // 手上有 token 就先送出（AuthContext 可能還在載入中），真的 401 再請使用者登入
  const canTry = (action: string) => {
    if (isAuthenticated || getAccessToken()) return true;
    askLogin(action);
    return false;
  };

  const toggleLike = async () => {
    if (!selectedWork || !canTry('按讚')) return;
    const { id, isLiked } = selectedWork;
    try {
      // POST 按讚、DELETE 收回；後端是冪等的，連點也不會把讚弄反
      const res = isLiked
        ? await api.delete<LikeResult>(`/club/works/${id}/like/`)
        : await api.post<LikeResult>(`/club/works/${id}/like/`);
      patchWork(id, res.data);
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 401) askLogin('按讚');
      else alert('操作失敗，請稍後再試');
    }
  };

  const addComment = async () => {
    const content = newComment.trim();
    if (!content || !selectedWork || !canTry('留言')) return;
    const workId = selectedWork.id;
    try {
      const res = await api.post<Comment>(`/club/works/${workId}/comments/`, { content });
      if (workId === selectedWorkId) setComments(prev => [...prev, res.data]);
      setWorks(prev => prev.map(w => (w.id === workId ? { ...w, commentCount: w.commentCount + 1 } : w)));
      setNewComment('');
    } catch (err) {
      if (isAxiosError<{ content?: string[] }>(err)) {
        if (err.response?.status === 401) return askLogin('留言');
        const reason = err.response?.data?.content?.[0];
        if (reason) return alert(reason);
      }
      alert('留言失敗，請稍後再試');
    }
  };

  const deleteComment = async (comment: Comment) => {
    if (!selectedWork || !window.confirm('確定要刪除這則留言嗎？')) return;
    const workId = selectedWork.id;
    try {
      await api.delete(`/club/comments/${comment.id}/`);
      setComments(prev => prev.filter(c => c.id !== comment.id));
      setWorks(prev => prev.map(w => (w.id === workId ? { ...w, commentCount: Math.max(w.commentCount - 1, 0) } : w)));
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 401) askLogin('刪除留言');
      else if (isAxiosError(err) && err.response?.status === 403) alert('只能刪除自己的留言');
      else alert('刪除失敗，請稍後再試');
    }
  };

  const toggleCommentLike = async (comment: Comment) => {
    if (!canTry('按讚')) return;
    try {
      const res = comment.isLiked
        ? await api.delete<LikeResult>(`/club/comments/${comment.id}/like/`)
        : await api.post<LikeResult>(`/club/comments/${comment.id}/like/`);
      setComments(prev => prev.map(c => (c.id === comment.id ? { ...c, ...res.data } : c)));
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 401) askLogin('按讚');
      else alert('操作失敗，請稍後再試');
    }
  };

  // 分頁邏輯
  const getPaginationItems = () => {
    const items = [];
    if (currentPage <= 3) {
      for (let i = 1; i <= Math.min(4, totalPages); i++) {
        items.push(i);
      }
      if (totalPages > 4) {
        items.push('...');
        items.push(totalPages);
      }
    } else if (currentPage >= totalPages - 2) {
      items.push(1);
      if (totalPages > 4) items.push('...');
      for (let i = Math.max(totalPages - 3, 1); i <= totalPages; i++) {
        items.push(i);
      }
    } else {
      items.push(1);
      items.push('...');
      for (let i = currentPage - 1; i <= currentPage + 1; i++) {
        items.push(i);
      }
      items.push('...');
      items.push(totalPages);
    }
    return items;
  };

  // 鍵盤事件處理
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // 正在輸入文字（例如留言框）時不要搶走按鍵
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable)
      ) {
        return;
      }
      if (selectedWork?.type === 'video') {
        switch (e.key) {
          case 'ArrowLeft':
            skipTime(-10);
            break;
          case 'ArrowRight':
            skipTime(10);
            break;
          case ' ':
            e.preventDefault();
            togglePlay();
            break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [selectedWork?.type, togglePlay, skipTime]);


  return (
    <div className="showcase-container">
      {/* 網站的側邊欄（右上角按鈕） */}
      <Sidebar />

      {/* 左側導航欄 */}
      <div className="sidebar">
        {/* 目前在看哪個社課的成果牆 */}
        <div className="works-heading">
          <Link to="/club" className="works-back">← 社課介紹</Link>
          <h1>{category ? `${categoryName(category)}成果牆` : '成果牆'}</h1>
          {category && <Link to={`/club/lessons?category=${category}`} className="works-lessons-link">看社課公告 →</Link>}
        </div>

        {courses.length > 0 && (
        <>
        {/* 排序標題 */}
        <div className="sort-header">
          <button 
            className="sort-button"
            onClick={toggleSort}
          >
            排序: {sortOption.type === 'time' ? '時間' : '熱度'}
          </button>
          <button onClick={toggleSortDirection} className="sort-direction-button">
            {sortOption.direction === 'desc' ? (
              <ChevronDown className="w-4 h-4 text-gray-500" />
            ) : (
              <ChevronUp className="w-4 h-4 text-gray-500" />
            )}
          </button>
        </div>

        {/* 導航列表容器 */}
        <div className="nav-container">
          <div 
            ref={courseListRef}
            className="nav-list"
          >
            {courses.map((course) => (
              <div
                key={course.id}
                className={`nav-item ${
                  selectedCourse === course.id
                    ? `nav-item-selected nav-item-${course.color}`
                    : ''
                }`}
                style={{
                  clipPath: selectedCourse === course.id 
                    ? 'polygon(0 0, calc(100% - 10px) 0, 100% 50%, calc(100% - 10px) 100%, 0 100%)' 
                    : 'polygon(0 0, calc(100% - 5px) 0, 100% 50%, calc(100% - 5px) 100%, 0 100%)'
                }}
                onClick={() => setSelectedCourse(course.id)}
              >
                <div className="nav-item-content">
                  {course.name}
                </div>
              </div>
            ))}
          </div>

          {/* 滾動控制按鈕（列表捲得動時才顯示） */}
          {canScroll && (
          <div className="scroll-controls">
            <button
              className="scroll-button"
              onClick={() => handleScroll('up')}
            >
              <ChevronUp className="w-3 h-3 text-gray-600" />
            </button>
            <button
              className="scroll-button"
              onClick={() => handleScroll('down')}
            >
              <ChevronDown className="w-3 h-3 text-gray-600" />
            </button>
          </div>
          )}
        </div>
        </>
        )}
        {!loading && courses.length === 0 && (
          <p className="works-side-empty">還沒有成果分類</p>
        )}
      </div>

      {/* 主要內容區 */}
      <div className="main-content">
        {!selectedWork ? (
          <div className="works-empty-state">
            {loading ? '載入中…' : (
              <div className="works-empty-card">
                <img src={PLACEHOLDER.empty} alt="" width={240} height={165} />
                <h2>
                  {loadError
                    ? '載入失敗'
                    : courses.length === 0
                      ? `${category ? categoryName(category) : ''}成果牆還沒有作品`
                      : '這個分類還沒有作品'}
                </h2>
                <p>
                  {loadError ?? '社課的作品、CM、照片整理好之後會放在這裡。可以先看看社課公告，知道最近在上什麼。'}
                </p>
                <div className="works-empty-actions">
                  {category && <Link to={`/club/lessons?category=${category}`} className="works-empty-button">看社課公告</Link>}
                  <Link to="/club" className="works-empty-button">其他社課</Link>
                  {canManage && <Link to="/club/works/manage" className="works-empty-button is-primary">上架作品</Link>}
                </div>
              </div>
            )}
          </div>
        ) : (
        <>
          {/* 內容標題欄 */}
          <div className="content-header">
            <div className="content-header-left">
              {selectedWork.author && (
                <div className="author-tag">
                  by {selectedWork.author}
                </div>
              )}
              {selectedWork.lesson && (
                <Link to={`/club/lessons/${selectedWork.lesson.id}`} className="author-tag lesson-tag">
                  來自 {selectedWork.lesson.number ? `第 ${selectedWork.lesson.number} 堂：` : ''}{selectedWork.lesson.title}
                </Link>
              )}
              <div className="title-container">
                <div className={`title ${selectedWork.title.length > 20 ? 'title-marquee' : ''}`}>
                  {selectedWork.title}
                </div>
              </div>
            </div>
          
            <div className="stats-container">
              <div className="stat-group">
                <button 
                  onClick={toggleLike}
                  className={`stat-button ${selectedWork.isLiked ? 'stat-button-liked' : ''}`}
                >
                  <ThumbsUp className="w-4 h-4" />
                </button>
                <span className="stat-count">{selectedWork.likes}</span>
              </div>
            
              <div className="stat-group">
                <button 
                  onClick={() => setShowComments(!showComments)}
                  className="stat-button"
                >
                  <MessageCircle className="w-4 h-4 text-gray-600" />
                </button>
                <span className="stat-count">{selectedWork.commentCount}</span>
              </div>
            
              <div className="stat-group">
                <Eye className="w-4 h-4 text-blue-400" />
                <span className="stat-count">{selectedWork.views}</span>
              </div>
            </div>
          </div>

          {/* 主要內容區域 */}
          <div className="content-body">
            {/* 媒體顯示區域 */}
            <div className="media-container">
              {!isGridView ? (
                <div className="media-viewer">
                  {selectedWork.embedUrl ? (
                    <div className="video-container">
                      <iframe
                        className="video-embed"
                        src={selectedWork.embedUrl}
                        title={selectedWork.title}
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowFullScreen
                      />
                    </div>
                  ) : selectedWork.type === 'video' ? (
                    <div className="video-container">
                      {/* 視頻播放器 */}
                      <div className="video-player">
                        <video 
                          ref={videoRef}
                          className="video-element"
                          src={selectedWork.url}
                          onClick={togglePlay}
                          onPlay={() => setIsPlaying(true)}
                          onPause={() => setIsPlaying(false)}
                          onEnded={() => setIsPlaying(false)}
                        />
                      </div>
                    
                      {/* 視頻控制欄 */}
                      <div className="video-controls">
                        <div className="video-controls-group">
                          {/* 音量控制 */}
                          <div className="volume-control">
                            <button 
                              onClick={toggleMute}
                              onMouseEnter={() => setShowVolumeSlider(true)}
                              onMouseLeave={() => setShowVolumeSlider(false)}
                              className="control-button"
                            >
                              {isMuted || volume === 0 ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
                            </button>
                          
                            {showVolumeSlider && (
                              <div 
                                className="volume-slider-container"
                                onMouseEnter={() => setShowVolumeSlider(true)}
                                onMouseLeave={() => setShowVolumeSlider(false)}
                              >
                                <input
                                  type="range"
                                  min="0"
                                  max="100"
                                  value={volume}
                                  onChange={(e) => handleVolumeChange(Number(e.target.value))}
                                  className="volume-slider"
                                />
                                <div className="volume-display">{volume}%</div>
                              </div>
                            )}
                          </div>

                          <button 
                            onClick={() => skipTime(-10)}
                            className="control-button"
                          >
                            <SkipBack className="w-5 h-5" />
                          </button>

                          <button 
                            onClick={togglePlay}
                            className="control-button"
                          >
                            {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6" />}
                          </button>

                          <button 
                            onClick={() => skipTime(10)}
                            className="control-button"
                          >
                            <SkipForward className="w-5 h-5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="image-viewer">
                      <img 
                        src={selectedWork.url || PLACEHOLDER.image}
                        onError={imageFallback}
                        alt={selectedWork.title}
                        className="image-element"
                      />
                    </div>
                  )}
                </div>
              ) : (
                /* 方格視圖 */
                <div className="grid-view">
                  {/* [更改處] 使用 works 替代 mockWorks */}
                  {works.map((work) => (
                    <div 
                      key={work.id}
                      className="grid-item"
                      onClick={() => {
                        setSelectedWorkId(work.id);
                        setIsGridView(false);
                      }}
                    >
                      <div className="grid-item-thumbnail">
                        <img
                          src={work.thumbnail || PLACEHOLDER[work.type]}
                          onError={work.type === 'video' ? videoFallback : imageFallback}
                          alt={work.title}
                          className="grid-thumbnail-image"
                          loading="lazy"
                        />
                        {work.type === 'video' && work.thumbnail && (
                          <span className="grid-play-badge" aria-hidden="true"><Play className="w-5 h-5" /></span>
                        )}
                      </div>
                      <div className="grid-item-info">
                        <h3 className="grid-item-title">{work.title}</h3>
                        <div className="grid-item-stats">
                          <span>👍 {work.likes}</span>
                          <span>👁 {work.views}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* 方格模式切換按鈕 */}
              {selectedWork.type === 'image' && (
                <button 
                  onClick={() => setIsGridView(!isGridView)}
                  className="grid-toggle-button"
                >
                  <Grid3x3 className="w-5 h-5 text-gray-600" />
                </button>
              )}
            </div>

            {/* 留言側邊欄 */}
            {showComments && (
              <div className="comments-sidebar">
                <div className="comments-header">
                  <h3 className="comments-title">留言 ({selectedWork.commentCount})</h3>
                </div>
              
                <div className="comments-list">
                  {comments.map((comment) => (
                    <div key={comment.id} className="comment-item">
                      <div className="comment-avatar">
                        {comment.username.slice(0, 1)}
                      </div>
                      <div className="comment-content">
                        <div className="comment-header">
                          <span className="comment-username">{comment.username}</span>
                          <button
                            className={`comment-like-button ${comment.isLiked ? 'comment-like-button-liked' : ''}`}
                            onClick={() => toggleCommentLike(comment)}
                            aria-pressed={comment.isLiked}
                          >
                            {comment.isLiked ? '❤️' : '🤍'} {comment.likes}
                          </button>
                          {comment.canDelete && (
                            <button
                              className="comment-delete-button"
                              onClick={() => deleteComment(comment)}
                              aria-label="刪除留言"
                            >
                              刪除
                            </button>
                          )}
                        </div>
                        <p className="comment-text">{comment.content}</p>
                      </div>
                    </div>
                  ))}
                </div>
              
                <div className="comment-input-container">
                  <div className="comment-input-group">
                    <input
                      type="text"
                      value={newComment}
                      onChange={(e) => setNewComment(e.target.value)}
                      placeholder="寫下你的留言..."
                      className="comment-input"
                      onKeyPress={(e) => e.key === 'Enter' && addComment()}
                    />
                    <button
                      onClick={addComment}
                      className="comment-submit-button"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 分頁導航 */}
          <div className="pagination-container">
            <button
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
              className="pagination-nav-button"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            {getPaginationItems().map((item, index) => (
              <React.Fragment key={index}>
                {item === '...' ? (
                  <span className="pagination-dots">...</span>
                ) : (
                  <button
                    onClick={() => setCurrentPage(item as number)}
                    className={`pagination-button ${
                      currentPage === item ? 'pagination-button-active' : ''
                    }`}
                  >
                    {item}
                  </button>
                )}
              </React.Fragment>
            ))}

            <button
              onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
              disabled={currentPage === totalPages}
              className="pagination-nav-button"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </>
        )}
      </div>
    </div>
  );
};

export default Works;