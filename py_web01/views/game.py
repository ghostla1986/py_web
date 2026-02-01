from flask import Blueprint,request,redirect,jsonify

#蓝图对象
ga = Blueprint("game",__name__)

@ga.route('/game',methods=["GET","POST"])
def game():
    """
    处理聊天请求
    前端会发送JSON数据，后端通过 request.json.get('message') 获取消息
    """
    try:
        # 获取JSON数据
        data = request.json
        
        if not data:
            return jsonify({'error': '请求必须包含JSON数据'}), 400
        
        # 获取消息内容
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': '消息不能为空'}), 400
        
        print(f"收到用户消息: {user_message}")
        
        # 简单的AI回复逻辑
        ai_reply = generate_sys_response(user_message)
        
        # 返回JSON响应
        return jsonify({
            'reply': ai_reply,
            'status': 'success'
        })
        
    except Exception as e:
        print(f"处理请求时出错: {str(e)}")
        return jsonify({'error': str(e)}), 500

def generate_sys_response(user_message):
    """简单的AI回复生成函数"""
    user_message_lower = user_message.lower()
    
    if any(word in user_message_lower for word in ["是", "yes","1"]):
        return f"好的，正在加载人物数据......"
    
    elif any(word in user_message_lower for word in ["否", "no", "2","没有","没"]):
        return "请输入[创建]建立游戏人物。"
    
    #elif "?" in user_message_lower:
        #return f"这是一个很好的问题：'{user_message}'"
    
    else:
        return f"无效指令，请勿自言自语。"
