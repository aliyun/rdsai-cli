#!/bin/bash
# installation script for rdsai-cli
# Installs via uv (https://docs.astral.sh/uv/)

set -u

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================
# Configuration & Constants
# ============================================
MIN_PYTHON_VERSION="3.13"
PACKAGE_NAME="rdsai-cli"
DEV_MODE=false
QUIET=false
PYTHON_VERSION=""
ORIGINAL_PATH=""  # Store original PATH at script start

# Common installation paths
readonly UV_INSTALL_PATHS=(
    "$HOME/.local/bin"
    "$HOME/.cargo/bin"
)

# URLs and timeouts
readonly UV_INSTALL_URL="https://astral.sh/uv/install.sh"
readonly CONNECTIVITY_CHECK_URL="https://astral.sh"
readonly CONNECTIVITY_TIMEOUT=5
readonly UV_INSTALL_TIMEOUT=30

# ============================================
# Utility Functions
# ============================================

# Print colored messages
info() {
    if [ "$QUIET" = false ]; then
        echo -e "${BLUE}ℹ${NC} $1"
    fi
}

success() {
    if [ "$QUIET" = false ]; then
        echo -e "${GREEN}✓${NC} $1"
    fi
}

warning() {
    if [ "$QUIET" = false ]; then
        echo -e "${YELLOW}⚠${NC} $1"
    fi
}

error() {
    echo -e "${RED}✗${NC} $1" >&2
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --python)
                PYTHON_VERSION="$2"
                shift 2
                ;;
            --dev)
                DEV_MODE=true
                shift
                ;;
            --quiet|-q)
                QUIET=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
installation script for rdsai-cli

Usage: $0 [OPTIONS]

This script automatically installs:
  1. uv (if not installed)
  2. Python 3.13+ (if not installed, via uv)
  3. rdsai-cli (via uv)

No manual installation required!

Options:
    --python VERSION     Specify Python version (default: 3.13)
    --dev                Install from source for development
    --quiet, -q          Quiet mode (minimal output)
    --help, -h           Show this help message

Examples:
    $0                          # Install rdsai-cli (auto-install uv and Python if needed)
    $0 --python 3.13            # Specify Python version
    $0 --dev                    # Install from source for development
EOF
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if directory is in PATH
is_dir_in_path() {
    local dir="$1"
    local path_to_check="${2:-$PATH}"
    case ":${path_to_check}:" in
        *:"$dir":*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Add directory to PATH if it exists and is not already in PATH
add_to_path_if_exists() {
    local dir="$1"
    if [ -d "$dir" ] && ! is_dir_in_path "$dir" "$PATH"; then
        export PATH="$dir:$PATH"
        return 0
    fi
    return 1
}

# Find uv binary in common installation paths
find_uv_in_paths() {
    local uv_path
    for uv_path in "${UV_INSTALL_PATHS[@]}"; do
        if [ -f "$uv_path/uv" ]; then
            echo "$uv_path"
            return 0
        fi
    done
    return 1
}

# Setup PATH for uv (add common paths and source env if available)
setup_uv_path() {
    local uv_path
    for uv_path in "${UV_INSTALL_PATHS[@]}"; do
        add_to_path_if_exists "$uv_path"
    done
    
    # Try to source uv env file if it exists (usually in first path)
    if [ -f "${UV_INSTALL_PATHS[0]}/env" ]; then
        source "${UV_INSTALL_PATHS[0]}/env" 2>/dev/null || true
    fi
}

# ============================================
# Python Installation Functions
# ============================================

# Check if Python is available (system Python or via uv)
check_python() {
    local target_version="${PYTHON_VERSION:-$MIN_PYTHON_VERSION}"
    
    # Check system Python first
    local python_cmd="python3"
    if command_exists "$python_cmd"; then
        local version=$($python_cmd --version 2>&1 | awk '{print $2}')
        local major=$(echo "$version" | cut -d. -f1)
        local minor=$(echo "$version" | cut -d. -f2)
        
        if [ "$major" -ge 3 ] && [ "$minor" -ge 13 ]; then
            success "Found system Python $version"
            return 0
        fi
    fi
    
    # Check if uv can provide the Python version
    if command_exists uv; then
        # Try to find Python via uv (this will succeed if Python is already installed via uv)
        if uv python find "${target_version}" >/dev/null 2>&1; then
            success "Python ${target_version} is available via uv"
            return 0
        fi
    fi
    
    return 1
}

# Install Python via uv
install_python() {
    local target_version="${PYTHON_VERSION:-$MIN_PYTHON_VERSION}"
    info "Installing Python ${target_version} via uv..."
    
    # Check network connectivity before installing Python
    if ! check_connectivity; then
        error "Cannot install Python without network connectivity."
        error "Please check your internet connection and try again."
        return 1
    fi
    
    if uv python install "${target_version}"; then
        success "Python ${target_version} installed successfully"
        return 0
    else
        error "Failed to install Python ${target_version} via uv"
        return 1
    fi
}

# Ensure Python is available
ensure_python() {
    local target_version="${PYTHON_VERSION:-$MIN_PYTHON_VERSION}"
    
    if check_python; then
        return 0
    fi
    
    # Python not found, install via uv
    if ! command_exists uv; then
        error "uv is required to install Python, but uv is not installed."
        error "Please ensure uv is installed first."
        exit 1
    fi
    
    info "Python ${target_version} is not available. Installing via uv..."
    if install_python; then
        return 0
    else
        return 1
    fi
}

# ============================================
# Installation Check Functions
# ============================================

# Check if rdsai is already installed
check_existing_installation() {
    if command_exists rdsai; then
        local version=$(rdsai --version 2>/dev/null || echo "unknown")
        warning "rdsai-cli is already installed (version: $version)"
        read -p "Do you want to reinstall? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Installation cancelled."
            exit 0
        fi
    fi
}

# ============================================
# uv Installation Functions
# ============================================

# Check if uv is installed
check_uv() {
    # First check if uv is in PATH
    if command_exists uv; then
        local version=$(uv --version 2>&1 | head -n1)
        success "Found uv: $version"
        return 0
    fi
    
    # Check common installation locations
    local uv_path=$(find_uv_in_paths)
    if [ -n "$uv_path" ]; then
        add_to_path_if_exists "$uv_path"
        if command_exists uv; then
            local version=$(uv --version 2>&1 | head -n1)
            success "Found uv: $version"
            return 0
        fi
    fi
    
    return 1
}

# Check network connectivity
check_connectivity() {
    info "Checking network connectivity..."
    
    if command_exists curl; then
        if curl -s --max-time "$CONNECTIVITY_TIMEOUT" --head "$CONNECTIVITY_CHECK_URL" >/dev/null 2>&1; then
            success "Network connectivity check passed"
            return 0
        fi
    elif command_exists wget; then
        if wget --spider --timeout="$CONNECTIVITY_TIMEOUT" --tries=1 "$CONNECTIVITY_CHECK_URL" >/dev/null 2>&1; then
            success "Network connectivity check passed"
            return 0
        fi
    else
        # If neither curl nor wget available, try ping as fallback
        if command_exists ping; then
            if ping -c 1 -W "$CONNECTIVITY_TIMEOUT" 8.8.8.8 >/dev/null 2>&1; then
                success "Network connectivity check passed"
                return 0
            fi
        fi
    fi
    
    error "Network connectivity check failed"
    error "Please check your internet connection and try again."
    return 1
}

# Install uv
install_uv() {
    info "Installing uv..."
    
    # Check network connectivity first
    if ! check_connectivity; then
        error "Cannot install uv without network connectivity."
        error "Please check your internet connection and try again."
        exit 1
    fi
    
    if command_exists curl; then
        if curl -LsSf --max-time "$UV_INSTALL_TIMEOUT" "$UV_INSTALL_URL" | sh; then
            # Installation script executed successfully
            :
        else
            error "Failed to download or execute uv installation script"
            exit 1
        fi
    elif command_exists wget; then
        if wget -qO- --timeout="$UV_INSTALL_TIMEOUT" "$UV_INSTALL_URL" | sh; then
            # Installation script executed successfully
            :
        else
            error "Failed to download or execute uv installation script"
            exit 1
        fi
    else
        error "Neither curl nor wget is available. Please install uv manually:"
        error "  curl -LsSf $UV_INSTALL_URL | sh"
        exit 1
    fi
    
    # Setup PATH for uv
    setup_uv_path
    
    # Verify uv is now available
    if command_exists uv; then
        success "uv installed successfully"
    else
        # Try to find uv in common paths
        local uv_path=$(find_uv_in_paths)
        if [ -n "$uv_path" ]; then
            error "uv was installed but not found in PATH"
            error "Please add one of these to your PATH:"
            for path in "${UV_INSTALL_PATHS[@]}"; do
                if [ -f "$path/uv" ]; then
                    error "  export PATH=\"$path:\$PATH\""
                fi
            done
            exit 1
        else
            error "Failed to install uv. Please install manually:"
            error "  curl -LsSf $UV_INSTALL_URL | sh"
            exit 1
        fi
    fi
}

# Ensure uv is installed
ensure_uv() {
    if check_uv; then
        return 0
    fi
    
    # Auto-install uv by default (always install if not found)
    info "uv is not installed. Installing uv..."
    if install_uv; then
        return 0
    else
        return 1
    fi
}

# ============================================
# rdsai-cli Installation Functions
# ============================================

# Install rdsai-cli via uv
install_rdsai() {
    info "Installing $PACKAGE_NAME via uv..."
    
    if [ "$DEV_MODE" = true ]; then
        error "Development mode installation from source requires manual setup."
        error "Please see README.md for development installation instructions."
        exit 1
    fi
    
    # Check network connectivity before installing package
    if ! check_connectivity; then
        error "Cannot install $PACKAGE_NAME without network connectivity."
        error "Please check your internet connection and try again."
        return 1
    fi
    
    local python_arg=""
    if [ -n "$PYTHON_VERSION" ]; then
        python_arg="--python $PYTHON_VERSION"
    else
        python_arg="--python $MIN_PYTHON_VERSION"
    fi
    
    # Run uv tool install and capture output
    local install_output
    install_output=$(uv tool install $python_arg "$PACKAGE_NAME" 2>&1)
    local install_status=$?
    
    # Check if installation was successful or package is already installed
    if [ $install_status -eq 0 ]; then
        success "$PACKAGE_NAME installed successfully"
        return 0
    elif echo "$install_output" | grep -q "already installed"; then
        # Package is already installed, this is fine
        success "$PACKAGE_NAME is already installed"
        return 0
    else
        error "Failed to install $PACKAGE_NAME"
        echo "$install_output" >&2
        return 1
    fi
}


# ============================================
# Verification & PATH Configuration Functions
# ============================================

# Get uv tool install directory
get_uv_tool_dir() {
    # Try to get the tool install directory from uv config
    local tool_dir=$(uv config get tool-install-dir 2>/dev/null || echo "")
    
    if [ -n "$tool_dir" ] && [ -d "$tool_dir" ]; then
        echo "$tool_dir"
        return 0
    fi
    
    # Fallback to default locations (check if rdsai exists)
    for dir in "${UV_INSTALL_PATHS[@]}"; do
        if [ -f "$dir/rdsai" ]; then
            echo "$dir"
            return 0
        fi
    done
    
    # Last resort: use default
    echo "${UV_INSTALL_PATHS[0]}"
}

# Verify installation
verify_installation() {
    info "Verifying installation..."
    
    # Get the actual tool install directory
    local tool_dir=$(get_uv_tool_dir)
    
    # Add common bin directories to PATH for verification
    add_to_path_if_exists "$tool_dir"
    setup_uv_path
    
    if command_exists rdsai; then
        local version=$(rdsai --version 2>/dev/null || echo "unknown")
        success "Installation verified! rdsai-cli version: $version"
        return 0
    else
        # Check if rdsai exists in tool_dir but not in PATH
        if [ -f "$tool_dir/rdsai" ]; then
            warning "rdsai is installed but not in PATH"
            return 1
        else
            warning "rdsai command not found"
            return 1
        fi
    fi
}

# Check if tool_dir is already configured in shell config files
is_configured_in_shell_files() {
    local tool_dir="$1"
    local shell_configs=(
        "$HOME/.bashrc"
        "$HOME/.bash_profile"
        "$HOME/.zshrc"
        "$HOME/.zshenv"
        "$HOME/.profile"
        "$HOME/.config/fish/config.fish"
    )
    
    for config_file in "${shell_configs[@]}"; do
        if [ -f "$config_file" ]; then
            # Check if tool_dir is explicitly added to PATH in config file
            # Match patterns like: export PATH="$tool_dir:$PATH" or export PATH="$tool_dir:$PATH"
            if grep -E "(export PATH=.*[\"']?$tool_dir[\"']?|PATH=.*[\"']?$tool_dir[\"']?)" "$config_file" 2>/dev/null | grep -q "PATH"; then
                return 0
            fi
            # Check if uv env file from tool_dir is sourced
            if [ -f "$tool_dir/env" ]; then
                # Match patterns like: source "$tool_dir/env" or source $tool_dir/env
                if grep -E "source.*[\"']?$tool_dir/env[\"']?" "$config_file" 2>/dev/null; then
                    return 0
                fi
            fi
            # Check if uv env.fish from tool_dir is sourced (for fish shell)
            if [ -f "$tool_dir/env.fish" ]; then
                if grep -E "source.*[\"']?$tool_dir/env\.fish[\"']?" "$config_file" 2>/dev/null; then
                    return 0
                fi
            fi
        fi
    done
    
    return 1
}

# Show PATH setup instructions
show_path_instructions() {
    local tool_dir=$(get_uv_tool_dir)
    
    local original_path="${ORIGINAL_PATH:-$PATH}"
    
    if is_dir_in_path "$tool_dir" "$original_path"; then
        return 0
    fi
    
    if is_configured_in_shell_files "$tool_dir"; then
        return 0
    fi
    
    echo ""
    echo "To add $tool_dir to your PATH, either restart your shell or run:"
    echo ""

    # Check if env file exists
    if [ -f "$tool_dir/env" ]; then
        echo "    source $tool_dir/env (sh, bash, zsh)"
    fi

    # Check if env.fish exists
    if [ -f "$tool_dir/env.fish" ]; then
        echo "    source $tool_dir/env.fish (fish)"
    fi

    # If no env files exist, show manual export
    if [ ! -f "$tool_dir/env" ] && [ ! -f "$tool_dir/env.fish" ]; then
        echo "    export PATH=\"$tool_dir:\$PATH\""
    fi

    echo ""
}


# ============================================
# Main Installation Function
# ============================================

# Main installation function
main() {
    # Save original PATH before any modifications
    ORIGINAL_PATH="$PATH"
    
    if [ "$QUIET" = false ]; then
        echo "================================"
        echo "  rdsai-cli Installation "
        echo "================================"
        echo
    fi
    
    # Parse arguments
    parse_args "$@"
    
    # Check existing installation
    check_existing_installation
    
    # Step 1: Ensure uv is installed
    if ! ensure_uv; then
        error "Failed to ensure uv is installed"
        exit 1
    fi
    
    # Step 2: Ensure Python is available (install via uv if needed)
    if ! ensure_python; then
        error "Failed to ensure Python is available"
        exit 1
    fi
    
    # Step 3: Install rdsai-cli
    if ! install_rdsai; then
        error "Installation failed!"
        exit 1
    fi
    
    # Post-installation
    if ! verify_installation; then
        warning "Installation verification failed, but installation may have succeeded."
        warning "Please check if rdsai command is available in your PATH."
    fi

    if [ "$QUIET" = false ]; then
        echo
        echo "=========================================="
        success "Installation completed!"
        echo "=========================================="
        
        show_path_instructions

        echo
        info "Next steps:"
        echo "  1. Run: rdsai"
        echo "  2. Configure LLM: /setup"
        echo "  3. Connect to database: /connect"
        echo
        info "For more information, visit: https://github.com/aliyun/rdsai-cli"
    fi
}

# Run main function
main "$@"

