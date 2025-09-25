import { useRef, useState, useEffect } from "react";
import { startSession, sendMessage, uploadDocument } from "./api";

function Dropdown({ open, anchorRight = false, children }) {
  if (!open) return null;
  return (
    <div className={`absolute ${anchorRight ? 'right-0' : 'left-0'} top-8 z-50 bg-white border border-gray-200 rounded-xl shadow-xl text-sm w-[18rem] sm:w-[22rem] lg:w-auto`}>{children}</div>
  );
}

export default function App() {
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState([]); // {sender, text, ts}
  const [input, setInput] = useState("");
  const [quickReplies, setQuickReplies] = useState([]);
  const [starting, setStarting] = useState(false);
  const [startName, setStartName] = useState("");
  const [startEmail, setStartEmail] = useState("");
  const [startPhone, setStartPhone] = useState("");
  const [validationErrors, setValidationErrors] = useState({});
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [loading, setLoading] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [showEmoji, setShowEmoji] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsPage, setSettingsPage] = useState("language");
  const [submenuTop, setSubmenuTop] = useState(0);
  const rootListRef = useRef(null);
  const fileRef = useRef(null);
  const listRef = useRef(null);

  const emojiList = ["😀","😁","😂","😊","😉","😍","🤩","👍","🙏","🎓","✈️","🇺🇸","🇬🇧","🇨🇦","🇦🇺"];

  const recalcSubmenuTop = () => {
    const list = rootListRef.current;
    if (!list) return;
    const active = list.querySelector('[data-active="true"]');
    if (active) {
      setSubmenuTop(active.offsetTop - list.scrollTop);
    }
  };

  const handleSettingsHover = (page, e) => {
    setSettingsPage(page);
    const list = rootListRef.current;
    if (list) {
      const target = e?.currentTarget;
      const off = target ? target.offsetTop : 0;
      setSubmenuTop(off - list.scrollTop);
    }
  };

  const autoScrollHover = (e) => {
    const el = rootListRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const y = e.clientY;
    const threshold = 20;
    if (y < rect.top + threshold) {
      el.scrollTop = Math.max(0, el.scrollTop - 12);
    } else if (y > rect.bottom - threshold) {
      el.scrollTop = Math.min(el.scrollHeight, el.scrollTop + 12);
    }
    recalcSubmenuTop();
  };

  useEffect(() => {
    recalcSubmenuTop();
  }, [settingsPage, settingsOpen]);

  const pushMsg = (m) => {
    setMessages((prev) => {
      const next = [...prev, { ...m, ts: new Date().toISOString() }];
      // auto-scroll on push
      queueMicrotask(() => {
        if (listRef.current) {
          listRef.current.scrollTop = listRef.current.scrollHeight;
          setShowScrollButton(false);
        }
      });
      return next;
    });
  };

  const handleScroll = () => {
    if (listRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = listRef.current;
      const isAtBottom = scrollTop + clientHeight >= scrollHeight - 10;
      setShowScrollButton(!isAtBottom);
    }
  };

  const scrollToBottom = () => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
      setShowScrollButton(false);
    }
  };

  const validateEmail = (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const validatePhone = (phone) => {
    const phoneRegex = /^[\+]?[0-9\s\-\(\)]{10,}$/;
    return phoneRegex.test(phone);
  };

  const startChat = async () => {
    const errors = {};
    if (!startName.trim()) errors.name = "Name is required";
    if (!startEmail.trim()) errors.email = "Email is required"; else if (!validateEmail(startEmail.trim())) errors.email = "Please enter a valid email address";
    if (!startPhone.trim()) errors.phone = "Phone is required"; else if (!validatePhone(startPhone.trim())) errors.phone = "Please enter a valid phone number";
    setValidationErrors(errors);
    if (Object.keys(errors).length > 0) return;
    try {
      setStarting(true);
      const data = await startSession(startName.trim(), startPhone.trim(), startEmail.trim());
      setSessionId(data.session_id);
      pushMsg({ sender: "bot", text: data.bot_message });
    } catch {
      pushMsg({ sender: "bot", text: "Unable to start session. Please try again." });
    } finally {
      setStarting(false);
    }
  };

  const onSend = async (overrideText) => {
    if (!sessionId) return;
    const text = (overrideText ?? input).trim();
    if (!text) return;
    const userMsg = { sender: "user", text };
    pushMsg(userMsg);
    if (overrideText === undefined) setInput("");
    setLoading(true);
    try {
      const res = await sendMessage(sessionId, userMsg.text);
      pushMsg({ sender: "bot", text: res.bot_message });
      setQuickReplies(Array.isArray(res.quick_replies) ? res.quick_replies : []);
    } catch {
      pushMsg({ sender: "bot", text: "Sorry, something went wrong." });
    } finally {
      setLoading(false);
    }
  };

  const onUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !sessionId) return;
    setLoading(true);
    try {
      await uploadDocument(sessionId, file);
      pushMsg({ sender: "bot", text: "Document received and queued for processing." });
    } catch {
      pushMsg({ sender: "bot", text: "Upload failed. Try again." });
    } finally {
      if (fileRef.current) fileRef.current.value = "";
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-2 sm:p-4">
      {/* Floating icon renders outside card so minimizing hides the card fully */}
      {minimized && (
        <button onClick={()=>setMinimized(false)} className="fixed bottom-4 right-4 z-50 w-14 h-14 rounded-full bg-gradient-to-r from-indigo-600 to-blue-600 text-white shadow-2xl flex items-center justify-center">
          💬
        </button>
      )}

      {!minimized && (
      <div className="w-full max-w-[min(100vw-1rem,1400px)] lg:max-w-[min(100vw-2rem,1400px)] bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden relative">
        {/* Header Section */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-4 py-3 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <div>
              <h1 className="text-sm font-semibold">Chat with Study Abroad Consultant</h1>
              <p className="text-xs text-blue-100">We're online</p>
            </div>
          </div>
          <div className="flex items-center space-x-2 relative">
            <div className="relative">
              <button onClick={()=>{setSettingsOpen((v)=>!v); setSettingsPage('root');}} className="p-1 hover:bg-white/20 rounded" title="Settings">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M11.983 1.843a1 1 0 00-1.966 0l-.09.542a7.967 7.967 0 00-1.45.84l-.5-.289a1 1 0 00-1.366.366l-.977 1.692a1 1 0 00.366 1.366l.5.289a7.967 7.967 0 000 1.68l-.5.289a1 1 0 00-.366 1.366l.977 1.692a1 1 0 001.366.366l.5-.289c.45.33.939.61 1.45.84l.09.542a1 1 0 001.966 0l.09-.542c.511-.23 1-.51 1.45-.84l.5.289a1 1 0 001.366-.366l.977-1.692a1 1 0 00-.366-1.366l-.5-.289a7.967 7.967 0 000-1.68l.5-.289a1 1 0 00.366-1.366l-.977-1.692a1 1 0 00-1.366-.366l-.5.289a7.967 7.967 0 00-1.45-.84l-.09-.542zM10 12a2 2 0 110-4 2 2 0 010 4z"/>
                </svg>
              </button>
              {/* Desktop (lg+): flyout submenu inside card but overlayed; Mobile/Tablet: in-panel two-column */}
              <div className="hidden lg:block">
                <Dropdown open={settingsOpen} anchorRight>
                  <div className="relative">
                    <div ref={rootListRef} className="w-56 max-h-64 overflow-y-auto no-scrollbar py-1 text-gray-800" onMouseMove={autoScrollHover}>
                      <button data-active={settingsPage==='language'} className="w-full text-left px-3 py-2 hover:bg-indigo-100" onMouseEnter={(e)=>handleSettingsHover('language', e)}>Change Language</button>
                      <button data-active={settingsPage==='theme'} className="w-full text-left px-3 py-2 hover:bg-indigo-100" onMouseEnter={(e)=>handleSettingsHover('theme', e)}>Change Theme</button>
                      <button data-active={settingsPage==='notifications'} className="w-full text-left px-3 py-2 hover:bg-indigo-100" onMouseEnter={(e)=>handleSettingsHover('notifications', e)}>Notification Preferences</button>
                      <div className="my-1 h-px bg-gray-200"/>
                      <button data-active={settingsPage==='profile'} className="w-full text-left px-3 py-2 hover:bg-indigo-100" onMouseEnter={(e)=>handleSettingsHover('profile', e)}>Update Student Profile</button>
                      <button data-active={settingsPage==='education'} className="w-full text-left px-3 py-2 hover:bg-indigo-100" onMouseEnter={(e)=>handleSettingsHover('education', e)}>Education Details</button>
                      <button data-active={settingsPage==='prefs'} className="w-full text-left px-3 py-2 hover:bg-indigo-100" onMouseEnter={(e)=>handleSettingsHover('prefs', e)}>Preferred Countries & Courses</button>
                      <div className="my-1 h-px bg-gray-200"/>
                      <button data-active={settingsPage==='privacy'} className="w-full text-left px-3 py-2 hover:bg-indigo-100" onMouseEnter={(e)=>handleSettingsHover('privacy', e)}>Privacy & Data</button>
                      <button data-active={settingsPage==='communication'} className="w-full text-left px-3 py-2 hover:bg-indigo-100" onMouseEnter={(e)=>handleSettingsHover('communication', e)}>Communication Preferences</button>
                    </div>
                    {/* Flush-attached submenu: render inside dropdown to the left of list to avoid overflow */}
                    <div className="absolute right-full bg-white border border-gray-200 rounded-xl shadow-xl p-3 text-sm text-gray-700" style={{ top: submenuTop }}>
                      {settingsPage === 'language' && (<div className="grid grid-cols-2 gap-1"><button className="px-2 py-1 rounded hover:bg-gray-50">English</button><button className="px-2 py-1 rounded hover:bg-gray-50">Urdu</button><button className="px-2 py-1 rounded hover:bg-gray-50">Arabic</button><button className="px-2 py-1 rounded hover:bg-gray-50">Chinese</button></div>)}
                      {settingsPage === 'theme' && (<div className="flex gap-2"><button className="px-2 py-1 rounded border hover:bg-gray-50">Light</button><button className="px-2 py-1 rounded border hover:bg-gray-50">Dark</button></div>)}
                      {settingsPage === 'notifications' && (<div className="space-y-1"><label className="flex items-center gap-2"><input type='checkbox'/> Sound</label><label className="flex items-center gap-2"><input type='checkbox'/> Popups</label><label className="flex items-center gap-2"><input type='checkbox'/> Reminders</label></div>)}
                      {settingsPage === 'profile' && (<div>Update name, email, phone.</div>)}
                      {settingsPage === 'education' && (<div>Qualification, grades, level.</div>)}
                      {settingsPage === 'prefs' && (<div>Countries and courses.</div>)}
                      {settingsPage === 'privacy' && (<div>Consent, clear chat, export.</div>)}
                      {settingsPage === 'communication' && (<div>Mode, WhatsApp/Email linking.</div>)}
                    </div>
                  </div>
                </Dropdown>
              </div>
              <div className="block lg:hidden">
                <Dropdown open={settingsOpen} anchorRight>
                  <div className="flex sm:flex-row flex-col">
                    <div ref={rootListRef} className="sm:w-1/2 w-full max-h-64 overflow-y-auto no-scrollbar py-1 text-gray-800" onMouseMove={autoScrollHover}>
                      <button className={`w-full text-left px-3 py-2 hover:bg-indigo-100 ${settingsPage==='language'?'bg-indigo-50':''}`} onMouseEnter={(e)=>handleSettingsHover('language', e)}>Change Language</button>
                      <button className={`w-full text-left px-3 py-2 hover:bg-indigo-100 ${settingsPage==='theme'?'bg-indigo-50':''}`} onMouseEnter={(e)=>handleSettingsHover('theme', e)}>Change Theme</button>
                      <button className={`w-full text-left px-3 py-2 hover:bg-indigo-100 ${settingsPage==='notifications'?'bg-indigo-50':''}`} onMouseEnter={(e)=>handleSettingsHover('notifications', e)}>Notification Preferences</button>
                      <div className="my-1 h-px bg-gray-200"/>
                      <button className={`w-full text-left px-3 py-2 hover:bg-indigo-100 ${settingsPage==='profile'?'bg-indigo-50':''}`} onMouseEnter={(e)=>handleSettingsHover('profile', e)}>Update Student Profile</button>
                      <button className={`w-full text-left px-3 py-2 hover:bg-indigo-100 ${settingsPage==='education'?'bg-indigo-50':''}`} onMouseEnter={(e)=>handleSettingsHover('education', e)}>Education Details</button>
                      <button className={`w-full text-left px-3 py-2 hover:bg-indigo-100 ${settingsPage==='prefs'?'bg-indigo-50':''}`} onMouseEnter={(e)=>handleSettingsHover('prefs', e)}>Preferred Countries & Courses</button>
                      <div className="my-1 h-px bg-gray-200"/>
                      <button className={`w-full text-left px-3 py-2 hover:bg-indigo-100 ${settingsPage==='privacy'?'bg-indigo-50':''}`} onMouseEnter={(e)=>handleSettingsHover('privacy', e)}>Privacy & Data</button>
                      <button className={`w-full text-left px-3 py-2 hover:bg-indigo-100 ${settingsPage==='communication'?'bg-indigo-50':''}`} onMouseEnter={(e)=>handleSettingsHover('communication', e)}>Communication Preferences</button>
                    </div>
                    <div className="sm:w-1/2 w-full border-l sm:block hidden border-gray-200 p-3 text-sm text-gray-700">
                      {settingsPage === 'language' && (<div className="grid grid-cols-2 gap-1"><button className="px-2 py-1 rounded hover:bg-gray-50">English</button><button className="px-2 py-1 rounded hover:bg-gray-50">Urdu</button><button className="px-2 py-1 rounded hover:bg-gray-50">Arabic</button><button className="px-2 py-1 rounded hover:bg-gray-50">Chinese</button></div>)}
                      {settingsPage === 'theme' && (<div className="flex gap-2"><button className="px-2 py-1 rounded border hover:bg-gray-50">Light</button><button className="px-2 py-1 rounded border hover:bg-gray-50">Dark</button></div>)}
                      {settingsPage === 'notifications' && (<div className="space-y-1"><label className="flex items-center gap-2"><input type='checkbox'/> Sound</label><label className="flex items-center gap-2"><input type='checkbox'/> Popups</label><label className="flex items-center gap-2"><input type='checkbox'/> Reminders</label></div>)}
                      {settingsPage === 'profile' && (<div>Update name, email, phone.</div>)}
                      {settingsPage === 'education' && (<div>Qualification, grades, level.</div>)}
                      {settingsPage === 'prefs' && (<div>Countries and courses.</div>)}
                      {settingsPage === 'privacy' && (<div>Consent, clear chat, export.</div>)}
                      {settingsPage === 'communication' && (<div>Mode, WhatsApp/Email linking.</div>)}
                    </div>
                    <div className="sm:hidden block border-t border-gray-200 p-3 text-sm text-gray-700">Select an option.</div>
                  </div>
                </Dropdown>
              </div>
            </div>
            <button onClick={()=>setMinimized(true)} className="p-1 hover:bg-white/20 rounded" title="Minimize">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4 10a1 1 0 011-1h10a1 1 0 110 2H5a1 1 0 01-1-1z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>

        {/* Start card OR chat */}
        {!sessionId ? (
          <div className="p-8">
            {/* Minimize control on start card too */}
            <button onClick={()=>setMinimized(true)} className="absolute top-2 right-2 p-2 text-white/90 hover:text-white">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M4 10a1 1 0 011-1h10a1 1 0 110 2H5a1 1 0 01-1-1z" clipRule="evenodd"/></svg>
            </button>
            <div className="space-y-6">
              <div className="text-center mb-8">
                <div className="w-16 h-16 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                </div>
                <h2 className="text-2xl font-bold text-gray-800 mb-2">Let's Get Started</h2>
                <p className="text-gray-600">Please provide your basic information to begin your study abroad journey</p>
              </div>
              {/* form fields unchanged ... */}
              <div className="space-y-5">
                {/* Name */}
                <div className="group">
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Full Name</label>
                  <div className="relative">
                    <input className={`w-full px-4 py-3 border-2 rounded-xl focus:ring-4 focus:ring-indigo-100 focus:border-indigo-500 outline-none transition-all duration-200 ${validationErrors.name ? 'border-red-300 bg-red-50' : 'border-gray-200 hover:border-gray-300 focus:border-indigo-500'}`} value={startName} onChange={(e)=>setStartName(e.target.value)} placeholder="Enter your full name"/>
                  </div>
                  {validationErrors.name && <p className="mt-1 text-xs text-red-600">{validationErrors.name}</p>}
                </div>
                {/* Email */}
                <div className="group">
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Email Address</label>
                  <div className="relative">
                    <input className={`w-full px-4 py-3 border-2 rounded-xl focus:ring-4 focus:ring-indigo-100 focus:border-indigo-500 outline-none transition-all duration-200 ${validationErrors.email ? 'border-red-300 bg-red-50' : 'border-gray-200 hover:border-gray-300 focus:border-indigo-500'}`} value={startEmail} onChange={(e)=>setStartEmail(e.target.value)} placeholder="your.email@example.com"/>
                  </div>
                  {validationErrors.email && <p className="mt-1 text-xs text-red-600">{validationErrors.email}</p>}
                </div>
                {/* Phone */}
                <div className="group">
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Phone Number</label>
                  <div className="relative">
                    <input className={`w-full px-4 py-3 border-2 rounded-xl focus:ring-4 focus:ring-indigo-100 focus:border-indigo-500 outline-none transition-all duration-200 ${validationErrors.phone ? 'border-red-300 bg-red-50' : 'border-gray-200 hover:border-gray-300 focus:border-indigo-500'}`} value={startPhone} onChange={(e)=>setStartPhone(e.target.value)} placeholder="+1 (555) 123-4567"/>
                  </div>
                  {validationErrors.phone && <p className="mt-1 text-xs text-red-600">{validationErrors.phone}</p>}
                </div>
              </div>
              <div className="pt-4">
                <button onClick={startChat} disabled={starting} className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-4 rounded-xl font-semibold text-lg hover:from-indigo-700 hover:to-purple-700 disabled:opacity-60 shadow-lg hover:shadow-xl transform hover:scale-[1.02] transition-all duration-200 flex items-center justify-center">
                  {starting ? (<><svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Starting your session...</>) : (<><svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>Start Your Journey</>)}
                </button>
              </div>
              <div className="text-center"><p className="text-sm text-gray-500">Your session will begin after you click Start</p></div>
            </div>
          </div>
        ) : (
          <>
            {/* Chat History Area */}
            <div className="relative h-[420px] sm:h-[480px] md:h-[560px] lg:h-[640px] bg-white">
              <div ref={listRef} onScroll={handleScroll} className="h-full overflow-y-auto px-4 py-4 space-y-3" style={{ scrollbarWidth: 'thin' }}>
                {messages.map((m, idx) => {
                  const isUser = m.sender === "user";
                  return (
                    <div key={idx} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] ${isUser ? 'order-2' : 'order-1'}`}>
                        <div className={`px-3 py-2 rounded-2xl ${isUser ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-800'}`}>
                          <p className="text-sm">{m.text}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
                {quickReplies?.length ? (
                  <div className="flex flex-wrap gap-2 justify-end">
                    {quickReplies.map((qr, i) => (
                      <button key={i} onClick={()=>onSend(qr)} className="text-xs bg-white border border-blue-200 text-blue-600 px-3 py-2 rounded-full hover:bg-blue-50 transition-colors">{qr}</button>
                    ))}
                  </div>
                ) : null}
              </div>
              {showScrollButton && (
                <button onClick={scrollToBottom} className="absolute bottom-4 left-1/2 transform -translate-x-1/2 w-8 h-8 bg-blue-500 text-white rounded-full shadow-lg hover:bg-blue-600 transition-colors flex items-center justify-center">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" /></svg>
                </button>
              )}
            </div>
            {/* Input Bar Section */}
            <div className="px-4 py-3 border-t bg-white">
              <div className="flex items-center space-x-2 relative">
                <label className={`cursor-pointer p-2 text-gray-500 hover:text-gray-700 transition-colors ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}>
                  <input ref={fileRef} type="file" className="hidden" onChange={onUpload} disabled={loading} />
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M8 4a3 3 0 00-3 3v4a5 5 0 0010 0V7a1 1 0 112 0v4a7 7 0 11-14 0V7a3 3 0 00-3-3z" clipRule="evenodd" /></svg>
                </label>
                <div className="relative">
                  <button onClick={()=>setShowEmoji((v)=>!v)} className="p-2 text-gray-500 hover:text-gray-700 transition-colors" type="button">
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM7 9a1 1 0 100-2 1 1 0 000 2zm7-1a1 1 0 11-2 0 1 1 0 012 0zm-.464 5.535a1 1 0 10-1.415-1.414 3 3 0 01-4.242 0 1 1 0 00-1.415 1.414 5 5 0 007.072 0z" clipRule="evenodd" /></svg>
                  </button>
                  {showEmoji && (
                    <div className="absolute bottom-10 left-0 z-20 bg-white border border-gray-200 rounded-xl shadow-xl p-2 grid grid-cols-6 gap-1 w-44">
                      {emojiList.map((e, i)=> (
                        <button key={i} className="hover:bg-gray-100 rounded p-1 text-base" onClick={()=>{setInput((t)=>t + e); setShowEmoji(false);}}>{e}</button>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex-1">
                  <input value={input} onChange={(e)=>setInput(e.target.value)} onKeyDown={(e)=>e.key === 'Enter' && onSend()} className="w-full border border-gray-300 rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder={loading ? 'Processing...' : 'Enter your message...'} disabled={loading} />
                </div>
                <button onClick={()=>onSend()} disabled={loading || !input.trim()} className="w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                  {loading ? (<svg className="animate-spin w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>) : (<svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" /></svg>)}
                </button>
              </div>
              <div className="text-center mt-2"><p className="text-xs text-gray-400"></p></div>
            </div>
          </>
        )}
      </div>
      )}
    </div>
  );
}
