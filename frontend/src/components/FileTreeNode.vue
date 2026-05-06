<template>
  <div class="file-tree-node">
    <div
      :class="['node-row', { 'is-dir': node.is_directory }]"
      :style="{ paddingLeft: (depth * 14 + 12) + 'px' }"
      @click="toggle"
    >
      <span class="node-icon">{{ nodeIcon }}</span>
      <span class="node-name">{{ node.name }}</span>
      <span v-if="node.is_directory" class="node-arrow">{{ expanded ? '▾' : '▸' }}</span>
    </div>
    <div v-if="expanded && node.children" class="node-children">
      <file-tree-node
        v-for="child in node.children"
        :key="child.name"
        :node="child"
        :depth="depth + 1"
      />
    </div>
  </div>
</template>

<script>
export default {
  name: 'FileTreeNode',
  props: {
    node: { type: Object, required: true },
    depth: { type: Number, default: 0 }
  },
  data() {
    return {
      expanded: this.depth < 1  // 默认展开第一层
    }
  },
  computed: {
    nodeIcon() {
      if (this.node.is_directory) {
        return this.expanded ? '📂' : '📁'
      }
      const ext = this.node.name.split('.').pop().toLowerCase()
      const iconMap = {
        'py': '🐍', 'js': '📜', 'vue': '💚', 'html': '🌐',
        'css': '🎨', 'md': '📝', 'json': '📋', 'txt': '📄',
        'db': '🗄️', 'env': '🔒', 'gitignore': '🚫', 'yml': '⚙️',
        'yaml': '⚙️', 'jpg': '🖼️', 'png': '🖼️', 'svg': '🖼️'
      }
      return iconMap[ext] || '📄'
    }
  },
  methods: {
    toggle() {
      if (this.node.is_directory) {
        this.expanded = !this.expanded
      }
    }
  }
}
</script>

<style scoped>
.node-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px 5px 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.12s;
  font-size: 13px;
  color: var(--on-surface);
  user-select: none;
}

.node-row:hover {
  background: var(--surface-container-high);
}

.node-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.node-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-arrow {
  font-size: 10px;
  color: var(--on-surface-variant);
  flex-shrink: 0;
}

.node-children {
  /* 子节点缩进由 paddingLeft 控制 */
}
</style>
