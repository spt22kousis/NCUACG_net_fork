import React, { useState, useRef, useEffect } from 'react';
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
import '../styles/Works.css';

// 類型定義
interface Course {
  id: string;
  name: string;
  color: 'blue' | 'green';
}

interface Work {
  id: string;
  title: string;
  type: 'video' | 'image';
  url: string;
  thumbnail?: string;
  likes: number;
  views: number;
  comments: Comment[];
  isLiked: boolean;
}

interface Comment {
  id: string;
  username: string;
  avatar: string;
  content: string;
  likes: number;
  isLiked: boolean;
}

interface SortOption {
  type: 'time' | 'popularity';
  direction: 'asc' | 'desc';
}

// 模擬數據
const courses: Course[] = [
  { id: 'about', name: '關於聲優社課', color: 'blue' },
  { id: '114-upper', name: '114上CM', color: 'blue' },
  { id: '114-upper-photos', name: '114上CM照片', color: 'blue' },
  { id: '113-lower', name: '113下CM', color: 'green' },
  { id: '113-lower-photos', name: '113下CM照片', color: 'green' },
  { id: '112-lower', name: '112下CM', color: 'blue' },
  { id: '112-lower-photos', name: '112下CM照片', color: 'blue' },
];

// [更改處] 保留原始模擬數據作為後備
const mockWorks: Work[] = [
  {
    id: '1',
    title: '聲優練習作品一號作品標題可能會很長需要跑馬燈效果',
    type: 'video',
    url: '#',
    likes: 25,
    views: 156,
    comments: [
      {
        id: '1',
        username: '小明',
        avatar: '👤',
        content: '很棒的作品！',
        likes: 3,
        isLiked: false
      }
    ],
    isLiked: false
  },
  {
    id: '2',
    title: '聲優練習圖片集',
    type: 'image',
    url: '#',
    likes: 18,
    views: 89,
    comments: [],
    isLiked: true
  }
];

const Works: React.FC = () => {
  // 狀態管理
  const [selectedCourse, setSelectedCourse] = useState<string>('about');
  // [更改處] 將 selectedWork 的初始值設為 null，稍後從 works 中選取
  const [selectedWork, setSelectedWork] = useState<Work | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages] = useState<number>(10);
  const [sortOption, setSortOption] = useState<SortOption>({ type: 'time', direction: 'desc' });
  const [showComments, setShowComments] = useState<boolean>(false);
  const [newComment, setNewComment] = useState<string>('');
  const [isGridView, setIsGridView] = useState<boolean>(false);
  // [更改處] 新增 works 狀態來儲存從後端獲取的數據
  const [works, setWorks] = useState<Work[]>(mockWorks);
  
  // 播放器相關狀態
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [volume, setVolume] = useState<number>(100);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [showVolumeSlider, setShowVolumeSlider] = useState<boolean>(false);
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const courseListRef = useRef<HTMLDivElement>(null);

  // [更改處] 新增 API 請求邏輯
  useEffect(() => {
    const fetchWorks = async () => {
      try {
        const response = await fetch('/api/works', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });
        if (!response.ok) {
          throw new Error('Failed to fetch works');
        }
        const data: Work[] = await response.json();
        // [更改處] 將後端數據儲存到 works 狀態（模擬暫存區 JSON）
        setWorks(data);
        // [更改處] 設定初始選中的作品
        setSelectedWork(data[0] || mockWorks[0]);
      } catch (error) {
        console.error('Error fetching works:', error);
        // [更改處] 若 API 請求失敗，回退到 mockWorks
        setWorks(mockWorks);
        setSelectedWork(mockWorks[0]);
      }
    };

    fetchWorks();
  }, []); // [更改處] 空依賴陣列，確保只在組件初次渲染時執行

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

  // 播放器控制
  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const skipTime = (seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime += seconds;
    }
  };

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
  const toggleLike = () => {
    // [更改處] 確保 selectedWork 存在
    if (selectedWork) {
      setSelectedWork(prev => ({
        ...prev!,
        likes: prev!.isLiked ? prev!.likes - 1 : prev!.likes + 1,
        isLiked: !prev!.isLiked
      }));
    }
  };

  const addComment = () => {
    if (newComment.trim() && selectedWork) {
      const comment: Comment = {
        id: Date.now().toString(),
        username: '當前使用者',
        avatar: '👤',
        content: newComment,
        likes: 0,
        isLiked: false
      };
      setSelectedWork(prev => ({
        ...prev!,
        comments: [...prev!.comments, comment]
      }));
      setNewComment('');
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
  }, [selectedWork?.type, isPlaying]);


  // [更改處] 確保 selectedWork 存在時才渲染主要內容
  if (!selectedWork) {
    return <div>Loading...</div>;
  }

  return (
    <div className="showcase-container">
      {/* 左側導航欄 */}
      <div className="sidebar">
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

          {/* 滾動控制按鈕 */}
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
        </div>
      </div>

      {/* 主要內容區 */}
      <div className="main-content">
        {/* 內容標題欄 */}
        <div className="content-header">
          <div className="content-header-left">
            <div className="author-tag">
              by 113CM組
            </div>
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
              <span className="stat-count">{selectedWork.comments.length}</span>
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
                {selectedWork.type === 'video' ? (
                  <div className="video-container">
                    {/* 視頻播放器 */}
                    <div className="video-player">
                      <video 
                        ref={videoRef}
                        className="video-element"
                        src={selectedWork.url}
                        onClick={togglePlay}
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
                      src={selectedWork.url || "data:image/svg+xml,%3Csvg width='400' height='300' xmlns='http://www.w3.org/2000/svg'%3E%3Crect width='100%25' height='100%25' fill='%23f0f0f0'/%3E%3Ctext x='50%25' y='50%25' font-family='Arial' font-size='18' fill='%23666' text-anchor='middle' dy='.3em'%3E圖片預覽%3C/text%3E%3C/svg%3E"}
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
                      setSelectedWork(work);
                      setIsGridView(false);
                    }}
                  >
                    <div className="grid-item-thumbnail">
                      {work.type === 'video' ? (
                        <Play className="w-8 h-8 text-gray-500" />
                      ) : (
                        <img 
                          src={work.thumbnail || "data:image/svg+xml,%3Csvg width='200' height='150' xmlns='http://www.w3.org/2000/svg'%3E%3Crect width='100%25' height='100%25' fill='%23e0e0e0'/%3E%3Ctext x='50%25' y='50%25' font-family='Arial' font-size='12' fill='%23666' text-anchor='middle' dy='.3em'%3E縮圖%3C/text%3E%3C/svg%3E"}
                          alt={work.title}
                          className="grid-thumbnail-image"
                        />
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
                <h3 className="comments-title">留言 ({selectedWork.comments.length})</h3>
              </div>
              
              <div className="comments-list">
                {selectedWork.comments.map((comment) => (
                  <div key={comment.id} className="comment-item">
                    <div className="comment-avatar">
                      {comment.avatar}
                    </div>
                    <div className="comment-content">
                      <div className="comment-header">
                        <span className="comment-username">{comment.username}</span>
                        <button className="comment-like-button">
                          ❤️ {comment.likes}
                        </button>
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
      </div>
    </div>
  );
};

export default Works;