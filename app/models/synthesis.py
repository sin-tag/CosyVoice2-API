"""Simplified Synthesis models for CosyVoice2 API - 跨语种复刻 (Cross-lingual Voice Cloning)"""
from typing import Optional
from pydantic import BaseModel, Field
from .voice import AudioFormat

# 跨语种复刻 - 带音频文件 (Cross-lingual with audio file)
class CrossLingualWithAudioRequest(BaseModel):
    """跨语种复刻 - 带音频文件"""
    text: str = Field(..., description="要合成的文本 (Text to synthesize)", max_length=2000)
    prompt_text: str = Field(..., description="输入prompt文本 (Reference text that matches the prompt audio)")
    prompt_audio_url: str = Field(..., description="参考音频文件路径 (URL or path to reference audio file)")
    instruct_text: Optional[str] = Field(None, description="输入instruct文本 (Optional instruction for voice style/emotion)")
    format: AudioFormat = Field(AudioFormat.WAV, description="输出音频格式")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="语速倍数")
    stream: bool = Field(False, description="是否流式推理 (默认: 否)")

# 跨语种复刻 - 使用缓存语音 (Cross-lingual with cached voice)
class CrossLingualWithCacheRequest(BaseModel):
    """跨语种复刻 - 使用缓存语音"""
    text: str = Field(..., description="要合成的文本 (Text to synthesize)", max_length=2000)
    voice_id: str = Field(..., description="缓存中的语音ID (Voice ID from cache)")
    prompt_text: Optional[str] = Field(None, description="输入prompt文本 (Optional prompt text for voice reference)")
    instruct_text: Optional[str] = Field(None, description="输入instruct文本 (Optional instruction for voice style/emotion)")
    format: AudioFormat = Field(AudioFormat.WAV, description="输出音频格式")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="语速倍数")
    stream: bool = Field(False, description="是否流式推理 (默认: 否)")

# 跨语种复刻 - 异步任务请求 (Cross-lingual async task)
class CrossLingualAsyncRequest(BaseModel):
    """跨语种复刻 - 异步任务请求"""
    text: str = Field(..., description="要合成的文本 (Text to synthesize)", max_length=2000)
    voice_id: str = Field(..., description="缓存中的语音ID (Voice ID from cache)")
    prompt_text: Optional[str] = Field(None, description="输入prompt文本 (Optional prompt text for voice reference)")
    instruct_text: Optional[str] = Field(None, description="输入instruct文本 (Optional instruction for voice style/emotion)")
    format: AudioFormat = Field(AudioFormat.WAV, description="输出音频格式")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="语速倍数")
    callback_url: Optional[str] = Field(None, description="完成后回调URL (Optional callback URL when completed)")

# 异步任务响应 (Async task response)
class AsyncTaskResponse(BaseModel):
    """异步任务响应"""
    success: bool = Field(..., description="任务创建是否成功")
    task_id: str = Field(..., description="任务ID")
    message: str = Field(..., description="响应消息")
    status: str = Field(..., description="任务状态: pending, processing, completed, failed")
    estimated_time: Optional[float] = Field(None, description="预估完成时间(秒)")

# 异步任务状态查询响应 (Async task status response)
class AsyncTaskStatusResponse(BaseModel):
    """异步任务状态查询响应"""
    success: bool = Field(..., description="查询是否成功")
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态: pending, processing, completed, failed")
    progress: float = Field(..., description="任务进度 (0.0-1.0)")
    message: str = Field(..., description="状态消息")
    audio_url: Optional[str] = Field(None, description="音频文件URL (仅completed状态)")
    file_path: Optional[str] = Field(None, description="音频文件路径 (仅completed状态)")
    duration: Optional[float] = Field(None, description="音频时长(秒) (仅completed状态)")
    synthesis_time: Optional[float] = Field(None, description="合成耗时(秒) (仅completed状态)")
    error_message: Optional[str] = Field(None, description="错误信息 (仅failed状态)")
    created_at: Optional[str] = Field(None, description="任务创建时间")
    completed_at: Optional[str] = Field(None, description="任务完成时间")

class SynthesisResponse(BaseModel):
    success: bool = Field(..., description="Whether synthesis was successful")
    message: str = Field(..., description="Response message")
    audio_url: Optional[str] = Field(None, description="URL to download the generated audio")
    file_path: Optional[str] = Field(None, description="Local file path to generated audio")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    format: AudioFormat = Field(..., description="Audio format")
    synthesis_time: Optional[float] = Field(None, description="Time taken for synthesis in seconds")

class AsyncSynthesisResponse(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Synthesis status")
    audio_url: Optional[str] = Field(None, description="URL to download the generated audio")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    format: AudioFormat = Field(..., description="Audio format")
    created_at: str = Field(..., description="Task creation timestamp")
    completed_at: Optional[str] = Field(None, description="Task completion timestamp")
    error: Optional[str] = Field(None, description="Error message if synthesis failed")
