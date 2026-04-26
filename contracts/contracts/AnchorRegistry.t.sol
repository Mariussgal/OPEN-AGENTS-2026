// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./AnchorRegistry.sol";

contract AnchorRegistryTest {
    AnchorRegistry registry;

    bytes32 constant PATTERN_HASH = keccak256("test-pattern");
    bytes32 constant ROOT_HASH = keccak256("test-root");

    function setUp() public {
        registry = new AnchorRegistry();
    }

    function test_AnchorNewPattern() public {
        registry.anchor(PATTERN_HASH, ROOT_HASH);
        assert(registry.isAnchored(PATTERN_HASH) == true);
    }

    function test_StoresCorrectData() public {
        registry.anchor(PATTERN_HASH, ROOT_HASH);
        (bytes32 root, address contributor, ) = registry.getAnchor(
            PATTERN_HASH
        );
        assert(root == ROOT_HASH);
        assert(contributor == address(this));
    }

    function test_IncrementsTotalAnchors() public {
        registry.anchor(PATTERN_HASH, ROOT_HASH);
        assert(registry.getTotalAnchors() == 1);
    }

    function test_IncrementsContributionCount() public {
        registry.anchor(PATTERN_HASH, ROOT_HASH);
        assert(registry.contributionCount(address(this)) == 1);
    }

    function test_ReturnsFalseForUnknownPattern() public view {
        assert(registry.isAnchored(keccak256("unknown")) == false);
    }

    function test_RevertsIfAlreadyAnchored() public {
        registry.anchor(PATTERN_HASH, ROOT_HASH);
        try registry.anchor(PATTERN_HASH, ROOT_HASH) {
            assert(false);
        } catch {
            assert(true);
        }
    }

    function test_RevertsGetAnchorUnknown() public view {
        try registry.getAnchor(keccak256("unknown")) {
            assert(false);
        } catch {
            assert(true);
        }
    }
}
