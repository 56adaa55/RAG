// src/components/Sidebar.jsx
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import ragLogo from '../assets/raglogo.png'

const Sidebar = () => {
  const location = useLocation();
  const links = [
    { to: "/load-file", text: "文档导入" },
    { to: "/chunk-file", text: "知识分块" },
    { to: "/parse-file", text: "文件解析" },
    { to: "/embedding", text: "向量存储" },
    { to: "/indexing", text: "向量库索引" },
    { to: "/search", text: "相似性检索" },
    { to: "/generation", text: "响应生成" }
  ];

  return (
    <div className="w-64 bg-gray-800 h-screen fixed left-0 top-0">
      <div className="p-4">
        <img 
          src={ragLogo} 
          alt="Logo" 
          className="w-full mb-6 rounded"
        />
      </div>
      <nav>
        {links.map(link => (
          <Link
            key={link.to}
            to={link.to}
            className={`block px-4 py-3 text-gray-300 hover:bg-gray-700 ${
              location.pathname === link.to ? 'bg-gray-700' : ''
            }`}
          >
            {link.text}
          </Link>
        ))}
      </nav>
      <div className="bg-black-500 text-white p-7">
            <h5 className="text-xs">在黄佳著的参考资料RAG框架项目上稍作修改 </h5>
      </div>
    </div>
  );
};

export default Sidebar;