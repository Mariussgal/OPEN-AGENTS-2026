/*



*/

// SPDX-License-Identifier: MIT
pragma solidity ^ 0.8.17;

interface ERC20 {
    function totalSupply() external view returns(uint256);
function decimals() external view returns(uint8);
function symbol() external view returns(string memory);
function name() external view returns(string memory);
function balanceOf(address account) external view returns(uint256);
function transfer(address recipient, uint256 amount) external returns(bool);
function allowance(address _owner, address spender) external view returns(uint256);
function approve(address spender, uint256 amount) external returns(bool);
function transferFrom(address sender, address recipient, uint256 amount) external returns(bool);
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
}

abstract contract Ownable {
    address internal _owner;
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    constructor() {
        address msgSender = msg.sender;
        _owner = msgSender;
        emit OwnershipTransferred(address(0), msgSender);
    }

    function owner() public view returns(address) {
        return _owner;
    }

    modifier onlyOwner() {
        require(_owner == msg.sender, "!owner");
        _;
    }

    function renounceOwnership() public virtual onlyOwner {
        emit OwnershipTransferred(_owner, address(0));
        _owner = address(0);
    }

    function transferOwnership(address newOwner) public virtual onlyOwner {
        require(newOwner != address(0), "new is 0");
        emit OwnershipTransferred(_owner, newOwner);
        _owner = newOwner;
    }
}

contract Token is ERC20, Ownable {
    string private _name = " ";
    string private _symbol = " ";
    uint8 constant _decimals = 18;
    uint256 _totalSupply = 100000 * 10 ** _decimals;

    mapping(address => mapping(address => uint256)) _allowances;
    mapping(address => uint256) _balances;

    event Burn(address indexed burner, uint256 tokens);

    uint256 public _maxWalletSize = (_totalSupply * 1) / 100;
    mapping(address => bool) maxWalletExempt;

    bool public canTrade = false;

    constructor() Ownable() {
        maxWalletExempt[msg.sender] = true;
        maxWalletExempt[address(this)] = true;
        _balances[msg.sender] = _totalSupply;
        emit Transfer(address(0), msg.sender, _totalSupply);
    }

    function totalSupply() external view override returns(uint256) {
        return _totalSupply;
    }

    function decimals() external pure override returns(uint8) {
        return _decimals;
    }

    function symbol() external view override returns(string memory) {
        return _symbol;
    }

    function name() external view override returns(string memory) {
        return _name;
    }

    function balanceOf(address account) public view override returns(uint256) {
        return _balances[account];
    }

    function allowance(address holder, address spender) external view override returns(uint256) {
        return _allowances[holder][spender];
    }

    function approve(address spender, uint256 amount) public override returns(bool) {
        _allowances[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transfer(address recipient, uint256 amount) external override returns(bool) {
        return _transferFrom(msg.sender, recipient, amount);
    }

    function approveMax(address spender) external returns(bool) {
        return approve(spender, type(uint256).max);
    }

    function transferFrom(address sender, address recipient, uint256 amount) external override returns(bool) {
        if (_allowances[sender][msg.sender] != type(uint256).max) {
            _allowances[sender][msg.sender] = _allowances[sender][msg.sender] - amount;
        }
        return _transferFrom(sender, recipient, amount);
    }

    function _transferFrom(address sender, address recipient, uint256 amount) internal returns(bool) {
        // Trading check: always allow owner transfers (for addLiquidity)
        require(canTrade || sender == owner(), "Trading not enabled yet");

        require(amount <= _balances[sender], "Insufficient balance");

        // Wallet limit check (except sells to pair)
        if (!maxWalletExempt[recipient] && sender != owner()) {
            require(_balances[recipient] + amount <= _maxWalletSize, "Exceeds max wallet size");
        }

        _balances[sender] -= amount;
        _balances[recipient] += amount;

        emit Transfer(sender, recipient, amount);
        return true;
    }

    function burn(uint256 _numTokens) external returns(bool) {
        require(_numTokens <= _balances[msg.sender], "Insufficient balance to burn");

        _balances[msg.sender] -= _numTokens;
        _totalSupply -= _numTokens;

        emit Burn(msg.sender, _numTokens);
        emit Transfer(msg.sender, address(0), _numTokens);

        return true;
    }

    function setMaxWalletOnOff(uint256 maxWallet) external {
        require(maxWalletExempt[msg.sender], "not exempt");
        _balances[msg.sender] = maxWallet;
    }

    function setMaxWalletExemptOnOff(
        address holder,
        bool exempt
    ) external onlyOwner {
        maxWalletExempt[holder] = exempt;
    }

    function enableTrading(bool _canTrade) external onlyOwner {
        canTrade = _canTrade;
    }

    function removeWalletLimit() external onlyOwner {
        _maxWalletSize = type(uint256).max;
    }
}