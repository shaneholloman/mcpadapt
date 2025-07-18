from pathlib import Path
from textwrap import dedent

import pytest
from mcp import StdioServerParameters

from mcpadapt.core import MCPAdapt
from mcpadapt.smolagents_adapter import SmolAgentsAdapter


@pytest.fixture
def echo_server_script():
    return dedent(
        '''
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("Echo Server")

        @mcp.tool()
        def echo_tool(text: str) -> str:
            """Echo the input text"""
            return f"Echo: {text}"
        
        mcp.run()
        '''
    )


@pytest.fixture
def echo_server_sse_script():
    return dedent(
        '''
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("Echo Server", host="127.0.0.1", port=8000)

        @mcp.tool()
        def echo_tool(text: str) -> str:
            """Echo the input text"""
            return f"Echo: {text}"

        mcp.run("sse")
        '''
    )


@pytest.fixture
def echo_server_optional_script():
    return dedent(
        '''
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("Echo Server")

        @mcp.tool()
        def echo_tool_optional(text: str | None = None) -> str:
            """Echo the input text, or return a default message if no text is provided"""
            if text is None:
                return "No input provided"
            return f"Echo: {text}"

        @mcp.tool()
        def echo_tool_default_value(text: str = "empty") -> str:
            """Echo the input text, default to 'empty' if no text is provided"""
            return f"Echo: {text}"

        @mcp.tool()
        def echo_tool_union_none(text: str | None) -> str:
            """Echo the input text, but None is not specified by default."""
            if text is None:
                return "No input provided"
            return f"Echo: {text}"
        
        mcp.run()
        '''
    )


@pytest.fixture
async def echo_sse_server(echo_server_sse_script):
    import subprocess
    import time

    # Start the SSE server process with its own process group
    process = subprocess.Popen(
        ["python", "-c", echo_server_sse_script],
    )

    # Give the server a moment to start up
    time.sleep(1)

    try:
        yield {"url": "http://127.0.0.1:8000/sse"}
    finally:
        # Clean up the process when test is done
        process.kill()
        process.wait()


def test_basic_sync(echo_server_script):
    with MCPAdapt(
        StdioServerParameters(
            command="uv", args=["run", "python", "-c", echo_server_script]
        ),
        SmolAgentsAdapter(),
    ) as tools:
        assert len(tools) == 1
        assert tools[0].name == "echo_tool"
        assert tools[0](text="hello") == "Echo: hello"


def test_basic_sync_sse(echo_sse_server):
    sse_serverparams = echo_sse_server
    with MCPAdapt(
        sse_serverparams,
        SmolAgentsAdapter(),
    ) as tools:
        assert len(tools) == 1
        assert tools[0].name == "echo_tool"
        assert tools[0](text="hello") == "Echo: hello"


def test_optional_sync(echo_server_optional_script):
    with MCPAdapt(
        StdioServerParameters(
            command="uv", args=["run", "python", "-c", echo_server_optional_script]
        ),
        SmolAgentsAdapter(),
    ) as tools:
        assert len(tools) == 3
        assert tools[0].name == "echo_tool_optional"
        assert tools[0](text="hello") == "Echo: hello"
        assert tools[0]() == "No input provided"
        assert tools[1].name == "echo_tool_default_value"
        assert tools[1](text="hello") == "Echo: hello"
        assert tools[1]() == "Echo: empty"
        assert tools[2].name == "echo_tool_union_none"
        assert tools[2](text="hello") == "Echo: hello"


def test_tool_name_with_dashes():
    mcp_server_script = dedent(
        '''
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("Echo Server")

        @mcp.tool(name="echo-tool")
        def echo_tool(text: str) -> str:
            """Echo the input text"""
            return f"Echo: {text}"
        
        mcp.run()
        '''
    )
    with MCPAdapt(
        StdioServerParameters(
            command="uv", args=["run", "python", "-c", mcp_server_script]
        ),
        SmolAgentsAdapter(),
    ) as tools:
        assert len(tools) == 1
        assert tools[0].name == "echo_tool"
        assert tools[0](text="hello") == "Echo: hello"


def test_tool_name_with_keyword():
    mcp_server_script = dedent(
        '''
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("Echo Server")

        @mcp.tool(name="def")
        def echo_tool(text: str) -> str:
            """Echo the input text"""
            return f"Echo: {text}"
        
        mcp.run()
        '''
    )
    with MCPAdapt(
        StdioServerParameters(
            command="uv", args=["run", "python", "-c", mcp_server_script]
        ),
        SmolAgentsAdapter(),
    ) as tools:
        assert len(tools) == 1
        assert tools[0].name == "def_"
        assert tools[0](text="hello") == "Echo: hello"


@pytest.fixture
def shared_datadir():
    return Path(__file__).parent / "data"


def test_image_tool(shared_datadir):
    mcp_server_script = dedent(
        f"""
        import os
        from mcp.server.fastmcp import FastMCP, Image

        mcp = FastMCP("Image Server")

        @mcp.tool("test_image")
        def test_image() -> Image:
            path = os.path.join("{shared_datadir}", "random_image.png")
            return Image(path=path, format='png')

        mcp.run()
        """
    )
    with MCPAdapt(
        StdioServerParameters(
            command="uv", args=["run", "python", "-c", mcp_server_script]
        ),
        SmolAgentsAdapter(),
    ) as tools:
        from PIL.ImageFile import ImageFile

        assert len(tools) == 1
        assert tools[0].name == "test_image"
        image_content = tools[0]()
        assert isinstance(image_content, ImageFile)
        assert image_content.size == (256, 256)


def test_audio_tool(shared_datadir):
    mcp_server_script = dedent(
        f"""
        import os
        import base64
        from mcp.server.fastmcp import FastMCP
        from mcp.types import AudioContent

        mcp = FastMCP("Audio Server")

        @mcp.tool("test_audio")
        def test_audio() -> AudioContent:
            path = os.path.join("{shared_datadir}", "white_noise.wav")
            with open(path, "rb") as f:
                wav_bytes = f.read()
        
            return AudioContent(type="audio", data=base64.b64encode(wav_bytes).decode(), mimeType="audio/wav")

        mcp.run()
        """
    )
    with MCPAdapt(
        StdioServerParameters(
            command="uv", args=["run", "python", "-c", mcp_server_script]
        ),
        SmolAgentsAdapter(),
    ) as tools:
        from torch import Tensor  # type: ignore

        assert len(tools) == 1
        assert tools[0].name == "test_audio"
        audio_content = tools[0]()
        assert isinstance(audio_content, Tensor)
