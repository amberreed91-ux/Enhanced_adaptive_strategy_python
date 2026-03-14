import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageCircle, X, Send, Loader2, Bot, User } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const AIAssistant = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hello! I'm your AI research assistant. Ask me anything about your trading strategies, market regimes, or research experiments." }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const { getAuthHeader } = useAuth();
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);

    try {
      const response = await axios.post(
        `${API}/chat/message`,
        { message: userMessage, session_id: sessionId },
        getAuthHeader()
      );
      setSessionId(response.data.session_id);
      setMessages(prev => [...prev, { role: "assistant", content: response.data.response }]);
    } catch (error) {
      setMessages(prev => [...prev, { 
        role: "assistant", 
        content: "Sorry, I encountered an error. Please try again." 
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {/* Toggle Button */}
      <Button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          fixed bottom-6 right-6 w-14 h-14 rounded-full shadow-lg z-50
          bg-primary hover:bg-primary/90 text-white
          ${isOpen ? "scale-0 opacity-0" : "scale-100 opacity-100"}
          transition-all duration-200
        `}
        data-testid="ai-assistant-toggle"
      >
        <MessageCircle className="w-6 h-6" />
      </Button>

      {/* Chat Panel */}
      <div
        className={`
          fixed bottom-6 right-6 w-96 h-[500px] z-50
          glass rounded-lg flex flex-col overflow-hidden
          ${isOpen ? "scale-100 opacity-100" : "scale-95 opacity-0 pointer-events-none"}
          transition-all duration-200 origin-bottom-right
        `}
        data-testid="ai-assistant-panel"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-primary" />
            <span className="font-medium text-sm">AI Research Assistant</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsOpen(false)}
            className="h-8 w-8"
            data-testid="ai-assistant-close"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Messages */}
        <ScrollArea className="flex-1 p-4" ref={scrollRef}>
          <div className="space-y-4">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
              >
                <div className={`
                  w-8 h-8 rounded-full flex items-center justify-center shrink-0
                  ${msg.role === "user" ? "bg-primary" : "bg-secondary"}
                `}>
                  {msg.role === "user" 
                    ? <User className="w-4 h-4" /> 
                    : <Bot className="w-4 h-4" />
                  }
                </div>
                <div className={`
                  max-w-[80%] px-3 py-2 rounded-lg text-sm
                  ${msg.role === "user" 
                    ? "bg-primary text-white" 
                    : "bg-secondary text-foreground"
                  }
                `}>
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="bg-secondary px-3 py-2 rounded-lg">
                  <Loader2 className="w-4 h-4 animate-spin" />
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input */}
        <div className="p-4 border-t border-white/10">
          <div className="flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask about strategies, signals..."
              className="flex-1 bg-secondary/50 border-transparent"
              data-testid="ai-assistant-input"
            />
            <Button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              size="icon"
              data-testid="ai-assistant-send"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
    </>
  );
};
